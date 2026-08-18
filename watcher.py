import time
import subprocess
import sys
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, script_path):
        self.script_path = os.path.abspath(script_path) # Normalize path
        self.process = None
        self.last_restart = 0
        self.debounce_seconds = 2 # Wait 2 seconds after last save
        self.start_process()

    def start_process(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3) # Wait up to 3s for clean exit
            except Exception:
                self.process.kill() # Force kill if stuck
        
        # Launch the actual script
        print(f"Starting: {self.script_path}")
        self.process = subprocess.Popen([sys.executable, self.script_path])

    def on_modified(self, event):
        if event.is_directory:
            return
            
        # Normalize event path for comparison
        event_path = os.path.abspath(event.src_path)
        
        if event_path == self.script_path:
            now = time.time()
            # Debounce: Ignore if restarted recently
            if now - self.last_restart < self.debounce_seconds:
                return
            
            print("Change detected, restarting...")
            self.last_restart = now
            self.start_process()

if __name__ == "__main__":
    # Use raw string or os.path.join for Windows safety
    script_dir = r"C:\youtube_title_updater"
    script_file = "auto_title_updater.py"
    script_to_run = os.path.join(script_dir, script_file)
    
    event_handler = ChangeHandler(script_to_run)
    observer = Observer()
    observer.schedule(event_handler, path=script_dir, recursive=False)
    observer.start()
    print(f"Watching for changes in {script_dir}...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if event_handler.process:
            event_handler.process.terminate()
    observer.join()