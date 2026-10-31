import subprocess
import sys
import time
import webbrowser

def main():
    print("Starting Intelli-Vitals Backend (FastAPI)...")
    backend = subprocess.Popen([sys.executable, "api.py"])
    
    time.sleep(2) # Wait for backend to start
    
    print("Starting Intelli-Vitals Dashboard (Streamlit)...")
    frontend = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard.py"]
    )
    
    time.sleep(3)
    print("\n" + "="*50)
    print("Dashboard is ready!")
    print("If your browser doesn't open automatically, please navigate to:")
    try:
        print("👉 http://localhost:8501 👈")
    except UnicodeEncodeError:
        print("-> http://localhost:8501 <-")
    print("="*50 + "\n")
    
    # Force open the default web browser
    webbrowser.open("http://localhost:8501")
    
    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        backend.terminate()
        frontend.terminate()

if __name__ == "__main__":
    main()
