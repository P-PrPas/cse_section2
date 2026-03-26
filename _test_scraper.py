import sys
from PyQt5.QtWidgets import QApplication
from dotenv import load_dotenv
import os
import cv2
from modules.ocsc_scraper import OcscScraperThread, ScraperStatus

def test_scraper():
    load_dotenv()
    user = os.environ.get("OCSC_USER", "eexamphoto")
    pwd = os.environ.get("OCSC_PASSWORD", "zLc3R/IZNfapHG5Idk2T3A==")
    
    app = QApplication(sys.argv)
    
    scraper = OcscScraperThread(user, pwd)
    
    def on_status(status, msg):
        print(f"[{status}] {msg}")
        if status == ScraperStatus.READY:
            # When ready, run a test search!
            test_id = input("Enter a 13-digit National ID to test (or enter to quit): ")
            if not test_id.strip():
                scraper.stop()
                app.quit()
            else:
                scraper.enqueue_search(test_id.strip())
                
    def on_finished(nat_id, img, err):
        if err:
            print(f"Error fetching {nat_id}: {err}")
        else:
            print(f"Successfully captured image for {nat_id} with shape {img.shape}")
            cv2.imshow("Scraped Image", img)
            cv2.waitKey(0) # Press any key to close
            cv2.destroyAllWindows()
            
        print("Ready for next ID.")
        
    scraper.status_changed.connect(on_status)
    scraper.search_finished.connect(on_finished)
    
    scraper.start()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    test_scraper()
