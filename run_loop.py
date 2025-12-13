import time
import subprocess
import sys
import datetime

def run_scraper():
    print(f"\n⏰ Starting Scraper Job at {datetime.datetime.now()}")
    try:
        # Run main.py using the same python interpreter
        result = subprocess.run([sys.executable, "news_project/main.py"], capture_output=False)
        if result.returncode == 0:
            print("✅ Job Finished Successfully.")
        else:
            print(f"❌ Job Failed with code {result.returncode}")
    except Exception as e:
        print(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    print("🚀 Auto-News-Scraper Started (Local Mode)")
    print("   Press Ctrl+C to stop.")
    
    # Run immediately on start
    run_scraper()
    
    while True:
        # Sleep for 6 hours (6 * 60 * 60 = 21600 seconds)
        # Or 24 hours for daily
        hours = 6
        print(f"💤 Sleeping for {hours} hours...")
        try:
            time.sleep(hours * 3600)
            run_scraper()
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break
