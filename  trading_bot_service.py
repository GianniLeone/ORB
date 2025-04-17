# trading_bot_service.py
# Windows service wrapper for the ORB News Trader

import os
import sys
import time
import logging
import subprocess
import signal
import servicemanager
import socket
import win32event
import win32service
import win32serviceutil
from pathlib import Path

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
Path(log_dir).mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "trading_service.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('trading_service')

class TradingBotService(win32serviceutil.ServiceFramework):
    _svc_name_ = "TradingBotService"
    _svc_display_name_ = "ORB News Trading Bot Service"
    _svc_description_ = "Automated trading bot service that combines ORB strategy with news sentiment analysis"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = False
        self.process = None
        
        # Get the directory where this script is located
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Scheduler script path
        self.scheduler_script = os.path.join(self.base_dir, "orb_news_scheduler.py")
        
        logger.info(f"Service initialized. Base directory: {self.base_dir}")
    
    def SvcStop(self):
        """Stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        
        # If process is running, try to terminate it gracefully
        if self.process:
            logger.info("Stopping scheduler process...")
            try:
                # Send CTRL+C signal to the process
                self.process.send_signal(signal.CTRL_C_EVENT)
                
                # Wait up to 10 seconds for the process to terminate
                for _ in range(10):
                    if self.process.poll() is not None:
                        logger.info("Process terminated gracefully")
                        break
                    time.sleep(1)
                
                # If still running, kill it
                if self.process.poll() is None:
                    logger.info("Process did not terminate gracefully, killing it")
                    self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping process: {e}")
                # Try to force kill if error
                try:
                    self.process.kill()
                except:
                    pass
        
        logger.info("Service stopped")
    
    def SvcDoRun(self):
        """Run the service"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        self.is_running = True
        self.main()
    
    def main(self):
        """Main service function"""
        logger.info("Starting Trading Bot Service")
        
        # Set the current directory to the base directory
        os.chdir(self.base_dir)
        logger.info(f"Working directory set to: {os.getcwd()}")
        
        # Make sure Python is in the path
        python_exe = sys.executable
        logger.info(f"Using Python: {python_exe}")
        
        while self.is_running:
            try:
                # Start the scheduler process
                logger.info("Starting scheduler process...")
                
                self.process = subprocess.Popen(
                    [python_exe, self.scheduler_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                
                logger.info(f"Scheduler process started with PID: {self.process.pid}")
                
                # Check if process is still alive every minute
                while self.is_running and self.process.poll() is None:
                    # Wait for the stop event or timeout
                    rc = win32event.WaitForSingleObject(self.hWaitStop, 60000)  # 60 seconds timeout
                    if rc == win32event.WAIT_OBJECT_0:
                        # Service received stop signal
                        logger.info("Service received stop signal")
                        self.is_running = False
                        break
                
                # If process has terminated but service is still running, check exit code
                if self.is_running and self.process.poll() is not None:
                    exit_code = self.process.poll()
                    stdout, stderr = self.process.communicate()
                    
                    logger.warning(f"Scheduler process terminated with exit code: {exit_code}")
                    
                    if stdout:
                        logger.info(f"Process stdout: {stdout.decode('utf-8', errors='ignore')[:1000]}")
                    if stderr:
                        logger.error(f"Process stderr: {stderr.decode('utf-8', errors='ignore')[:1000]}")
                    
                    # Wait before restarting
                    logger.info("Waiting 60 seconds before restarting scheduler...")
                    rc = win32event.WaitForSingleObject(self.hWaitStop, 60000)  # 60 seconds timeout
                    if rc == win32event.WAIT_OBJECT_0:
                        # Service received stop signal
                        self.is_running = False
                        break
            
            except Exception as e:
                logger.error(f"Error in service main loop: {e}")
                # Wait before retrying
                win32event.WaitForSingleObject(self.hWaitStop, 60000)  # 60 seconds timeout
        
        logger.info("Main service loop terminated")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TradingBotService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(TradingBotService)