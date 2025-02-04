import json
import os
import zipfile
import hashlib
import logging
from datetime import datetime
import time
from typing import Dict, Set, Optional, Tuple
from urllib.parse import urlparse
from fuzzywuzzy import fuzz
import base64
import gzip

from botasaurus.browser import Driver, cdp
from botasaurus_driver.core import util
from botasaurus_driver.core.env import is_docker
from botasaurus_driver.core.browser import Browser, terminate_process, wait_for_graceful_close, delete_profile

class AutomationError(Exception):
    """Custom exception for wallet automation errors"""
    pass

def setup_logging():
    """Configure logging with custom format and both file and console handlers."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'tmp/automation_{timestamp}.log'
    
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def find_project_root():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if os.path.isdir(os.path.join(current_dir, ".git")):
            return current_dir  # Found the Git project root
        current_dir = os.path.dirname(current_dir)  # Move up one directory
    # Fallback path (adjust if necessary)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

def generate_extension_id(extension_path: str) -> str:
    """Generates the extension ID for an unpacked Chrome extension."""
    logger.info("Generating extension ID...")
    try:
        normalized_path = os.path.normpath(extension_path)
        m = hashlib.sha256()
        m.update(normalized_path.encode('utf-8'))
        ext_id = ''.join([chr(int(i, base=16) + ord('a')) for i in m.hexdigest()][:32])
        logger.info(f"Extension ID generated successfully: {ext_id}")
        return ext_id
    except Exception as e:
        logger.error(f"Failed to generate extension ID: {str(e)}")
        raise AutomationError(f"Failed to generate extension ID: {str(e)}")

class FileMatcher:
    def __init__(self):
        self.minimum_score = 60  # Minimum fuzzy match score (0-100)

    def get_best_match(self, query: str, candidates: list[str], download_dir: str) -> Tuple[Optional[str], int]:
        """
        Find the best matching filename using both fuzzy matching and content checking.
        Returns tuple of (best_match, score)
        """
        best_match = None
        best_score = 0

        # Extract domain and searchable parts from query
        query_parts = self._extract_searchable_parts(query)
        domain = self._extract_domain(query)
        
        for candidate in candidates:
            # First check content match
            filepath = os.path.join(download_dir, candidate)
            content_match_score = self._check_content_match(filepath, domain, query)
            
            # Then check filename match
            filename_scores = [fuzz.partial_ratio(part.lower(), candidate.lower()) 
                             for part in query_parts]
            filename_score = max(filename_scores) if filename_scores else 0
            
            # Combine scores - weight content match more heavily
            final_score = (content_match_score * 0.7) + (filename_score * 0.3)
            
            if final_score > best_score and final_score >= self.minimum_score:
                best_score = final_score
                best_match = candidate

        return best_match, int(best_score)

    def _check_content_match(self, filepath: str, domain: str, url: str) -> float:
        """
        Check if the URL or domain appears in the file content.
        Returns a score from 0-100.
        """
        try:
            # Read first 1MB of file to check for URL/domain
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024 * 1024)
                
            # Check for exact URL match
            if url in content:
                return 100
                
            # Check for domain match
            if domain and domain in content:
                return 80
                
            # Check for partial URL match
            url_parts = url.split('/')
            matches = sum(1 for part in url_parts if part and part in content)
            if matches:
                return min(60 + (matches * 10), 90)
                
            return 0
            
        except Exception as e:
            logging.warning(f"Error checking file content for {filepath}: {str(e)}")
            return 0

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None

    def _extract_searchable_parts(self, url: str) -> list[str]:
        """Extract various parts from URL that might match filename."""
        try:
            parsed = urlparse(url)
            parts = []
            
            # Add domain without TLD
            domain = parsed.netloc.split('.')
            if len(domain) > 1:
                parts.append(domain[-2])  # Main domain name
            
            # Add full domain
            parts.append(parsed.netloc)
            
            # Add path parts
            path_parts = [p for p in parsed.path.split('/') if p]
            parts.extend(path_parts)
            
            return list(filter(None, parts))
        except Exception:
            return [url]

class DownloadTracker:
    def __init__(self, download_dir: str, urls: list):
        self.download_dir = download_dir
        self.urls = set(urls)
        self.downloaded_files: Set[str] = set()
        self.url_to_file_mapping: Dict[str, str] = {}
        self.initial_files = set(os.listdir(download_dir))
        self.file_matcher = FileMatcher()
        
    def check_new_downloads(self) -> bool:
        """Check for new downloads and map them to URLs using fuzzy matching."""
        current_files = set(os.listdir(self.download_dir))
        new_files = current_files - self.initial_files - self.downloaded_files

        # Dynamically wait for .crdownload files to finish
        while any(file.endswith('.crdownload') for file in new_files):
            print("Waiting for .crdownload files to complete...")
            # Check for changes every second, adjust as needed
            current_files_temp = set(os.listdir(self.download_dir))
            if current_files_temp == current_files:
                # If no change in files, break to avoid infinite loop
                break
            current_files = current_files_temp
            new_files = current_files - self.initial_files - self.downloaded_files
        
        if new_files:
            # Check each unmatched URL against new files
            for url in self.urls:
                if url in self.url_to_file_mapping:
                    continue

                best_match, score = self.file_matcher.get_best_match(url, list(new_files), self.download_dir)

                if best_match:
                    self.url_to_file_mapping[url] = best_match
                    self.downloaded_files.add(best_match)
                    logger.info(f"Matched URL {url} to file {best_match} (score: {score})")
                    
                    # Quick content check - verify file is readable and has content
                    filepath = os.path.join(self.download_dir, best_match)
                    if not self._verify_file(filepath):
                        logger.warning(f"File verification failed for {filepath}")
                        self.url_to_file_mapping.pop(url)
                        self.downloaded_files.remove(best_match)
        
        return len(self.url_to_file_mapping) == len(self.urls)

    def _verify_file(self, filepath: str) -> bool:
        """Basic verification that file exists and has content."""
        try:
            if not os.path.exists(filepath):
                return False
                
            # Check file is complete and readable
            with open(filepath, 'rb') as f:
                # Read first few bytes to verify content exists
                content = f.read(1024)
                return bool(content)
        except (IOError, PermissionError):
            return False
        except Exception as e:
            logger.error(f"Error verifying file {filepath}: {str(e)}")
            return False

    def get_url_mapping_with_content(self) -> Dict[str, Dict]:
        """
        Returns a dictionary mapping URLs to file details including compressed and encoded content.
        """
        url_mapping = {}
        for url, filename in self.url_to_file_mapping.items():
            filepath = os.path.join(self.download_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Compress the content
                compressed_content = gzip.compress(content.encode('utf-8'))

                # Encode the compressed content in base64
                encoded_content = base64.b64encode(compressed_content).decode('utf-8')

                url_mapping[url] = {
                    'filename': filename,
                    'content': encoded_content
                }
            except Exception as e:
                logger.error(f"Error reading or encoding content from {filepath}: {str(e)}")
                url_mapping[url] = {
                    'filename': filename,
                    'content': None,
                    'error': str(e)
                }
        return url_mapping

def main(extension_crx="mpiodijhokgodhhofbcjdecpffjipkle.crx",
               extension_directory="unpacked_extension", 
               urls_to_download=["https://google.com", "https://github.com", "https://youtube.com"]):
    global logger
    logger = setup_logging()
    logger.info("Starting wallet automation process...")
    
    browser = None
    tracker = None
    try:
        # Check if environment variables are set; if not, use defaults relative to current working directory.
        download_dir = os.environ.get("DOWNLOAD_DIR", os.path.join(os.getcwd(), 'snapshots'))
        extension_dir = os.environ.get("EXTENSION_DIR", os.path.join(os.getcwd(), extension_directory))
        
        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(extension_dir, exist_ok=True)
        
        # Initialize download tracker
        tracker = DownloadTracker(download_dir, urls_to_download)

        logger.info(f"Using extension directory: {extension_dir}")
        logger.info(f"Using download directory: {download_dir}")
        
        # Unpack extension
        logger.info("Unpacking extension...")
        try:
            with zipfile.ZipFile(extension_crx, 'r') as zip_ref:
                zip_ref.extractall(extension_dir)
            logger.info("Extension unpacked successfully")
        except zipfile.BadZipFile:
            logger.error("Invalid or corrupted extension file")
            raise AutomationError("Invalid or corrupted extension file")

        extension_id = generate_extension_id(extension_dir)
        extension_url = f"chrome-extension://{extension_id}/src/ui/pages/batch-save-urls.html"
        args = [
                f"--disable-extensions-except={extension_dir}",
                f"--load-extension={extension_dir}",
                f"--download.default_directory={download_dir}",
                "--enable-logging=stderr",
                "--v=1",
                "--log-level=0"
            ]
        # Launch browser
        logger.info("Launching browser...")
        driver = Driver(arguments=args)
       
        
        logger.info("Browser launched successfully")

        # Handle pages
        logger.info("Opening extension page...")
        tab = driver.get(extension_url)
        tab.wait_for('#URLLabel')
       
        download_cdp_config = cdp.browser.set_download_behavior(behavior='allow', download_path=download_dir, events_enabled=True)
        tab.run_cdp_command(download_cdp_config)
        tab.sleep(2)
        
        # Trigger downloads
        tab.evaluate('console.log("Starting downloads...");')
        tab.evaluate(f'let res = browser.runtime.sendMessage({{ method: "downloads.saveUrls", urls: {urls_to_download} }});')

        # Wait for downloads to complete
        logger.info("Waiting for downloads to complete...")
        max_wait_time = 300  # 5 minutes timeout
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            if tracker.check_new_downloads():
                logger.info("All downloads completed successfully!")
                logger.info("URL to file mapping:")
                for url, file in tracker.url_to_file_mapping.items():
                    logger.info(f"{url} -> {file}")
                break
            tab.sleep(1)
            
        if time.time() - start_time >= max_wait_time:
            logger.error("Timeout waiting for downloads to complete")
            raise AutomationError("Download timeout")
        
        # Return the URL mapping with content
        return tracker.get_url_mapping_with_content()

    except Exception as e:
        logger.error(f"Error during automation: {str(e)}")
        raise
    finally:
       
        if driver:
            ## hacky but botosaurus has a bug when closing the browser
            try:
                close(driver._browser)
            except Exception as e:
                print(e)
            
            logger.info("Browser closed")

def close(browser: Browser):
    # close gracefully
    if browser.connection:
        browser.connection.send(cdp.browser.close())
    
    browser.close_tab_connections()
    browser.close_browser_connection()

   
    if browser._process:
        if not wait_for_graceful_close(browser._process):
            terminate_process(browser._process)
    browser._process = None
    browser._process_pid = None

    if browser.config.is_temporary_profile:
        delete_profile(browser.config.profile_directory)
    browser.config.close()
    instances = util.get_registered_instances()
    try:
        instances.remove(browser)
    except KeyError:
        pass

    if is_docker:
        util.close_zombie_processes()

def lambda_handler(event, context):
    """
    Lambda function handler to trigger the download process.

    Args:
        event (dict): Event data passed to the Lambda function. 
                      Expected format:
                      {
                          "urls": ["https://google.com", "https://github.com", ...]
                      }
        context (object): Lambda context object.

    Returns:
        dict: A dictionary containing the status and URL mappings.
    """
    logger = setup_logging()
    logger.info("Lambda function invoked.")

    # Extract URLs from the event
    urls_to_download = event.get("urls", [])
    if not urls_to_download:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'No URLs provided in the event.'})
        }

    # Set environment variables for download directory within Lambda (/tmp is writable)
    os.environ['DOWNLOAD_DIR'] = '/tmp/snapshots'
    os.environ['EXTENSION_DIR'] = '/tmp/unpacked_extension'
    
    # Ensure directories exist
    os.makedirs(os.environ['DOWNLOAD_DIR'], exist_ok=True)
    os.makedirs(os.environ['EXTENSION_DIR'], exist_ok=True)

    try:
        # Find project root to locate the CRX file.
        project_root = find_project_root()

        # Construct the extension CRX file path.
        extension_crx = os.path.join(project_root, "tmp", "mpiodijhokgodhhofbcjdecpffjipkle.crx")

        # Run the main function asynchronously and get the URL mapping
        url_mappings = main(extension_crx=extension_crx,
                                          extension_directory=os.environ['EXTENSION_DIR'],
                                          urls_to_download=urls_to_download)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Downloads completed successfully.',
                'url_mappings': url_mappings
            })
        }
    except Exception as e:
        logger.error(f"Error in Lambda function: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
    
if __name__ == '__main__':
    main()