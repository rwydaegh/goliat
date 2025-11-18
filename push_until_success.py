#!/usr/bin/env python3
"""Keep trying git push until it succeeds, then play a sound."""

import subprocess
import sys
import time
import winsound

def play_success_sound():
    """Play a success sound on Windows."""
    try:
        # Play a pleasant beep sequence
        winsound.Beep(800, 200)  # Higher pitch
        time.sleep(0.1)
        winsound.Beep(1000, 300)  # Even higher pitch, longer
    except Exception:
        # Fallback: just print
        print("\a")  # ASCII bell

def main():
    """Main loop: retry git push until success."""
    attempt = 0
    
    print("Starting git push retry loop...")
    print("Press Ctrl+C to cancel")
    print()
    
    while True:
        attempt += 1
        print(f"Attempt {attempt}: Pushing to remote...", end=" ", flush=True)
        
        try:
            result = subprocess.run(
                ["git", "push"],
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            if result.returncode == 0:
                print("✓ SUCCESS!")
                print()
                print(result.stdout)
                print()
                print("🎉 Push completed successfully!")
                play_success_sound()
                sys.exit(0)
            else:
                print("✗ Failed")
                if result.stderr:
                    print(f"Error: {result.stderr.strip()}")
                print(f"Waiting 5 seconds before retry...")
                time.sleep(5)
                
        except subprocess.TimeoutExpired:
            print("✗ Timeout")
            print("Waiting 5 seconds before retry...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n\nCancelled by user.")
            sys.exit(1)
        except Exception as e:
            print(f"✗ Error: {e}")
            print("Waiting 5 seconds before retry...")
            time.sleep(5)

if __name__ == "__main__":
    main()

