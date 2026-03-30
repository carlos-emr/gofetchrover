import requests
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from requests.exceptions import SSLError
import json
import shutil
import sys
import time
import logging

script_dir = "/volumes/rover/"

log_file = "/volumes/rover/gfr.log"

# Create a logger
logger = logging.getLogger(__name__)

# Define the lock file path
lock_file = script_dir + 'rover.lock'

# Construct the path to the configuration file
config_path = os.path.join(script_dir, 'rover_config.json')

# Load the configuration file
def load_config(config_file):
    try:
        with open(config_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error(f"File not found: {config_file}")
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from the file: {config_file}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

# Load the configuration
config = load_config(config_path)

# Access the configuration values
base_url = config["base_url"]
user_id = config["user_id"]
password = config["password"]
client_cert_path = config["client_cert_path"]
root_cert_path = config["root_cert_path"]
client_key_path = config["client_key_path"]
incoming_HL7_folder_path = config["incoming_HL7_folder_path"]
incoming_xml_folder_path = config["incoming_xml_folder_path"]
incomingMuleFolder = config["incomingMuleFolder"]
app_name = config["app_name"]
app_version = config["app_version"]
verification_interval = config["verification_interval"]
mule_log_file = "/mule/logs/mule.log"

# Log level: configurable via rover_config.json, defaults to DEBUG
log_level_name = config.get("log_level", "DEBUG").upper()
log_level = getattr(logging, log_level_name, logging.DEBUG)

logging.basicConfig(filename=log_file, level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

def is_locked():
    """Check if the lock file exists."""
    return os.path.exists(lock_file)

def create_lock():
    """Create the lock file."""
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))  # Store the process ID in the lock file

def remove_lock():
    """Remove the lock file."""
    os.remove(lock_file)

def verify_file_on_disk(file_path, expected_min_size=1):
    """Verify a file exists on disk and has content."""
    if not os.path.exists(file_path):
        logger.error(f"VERIFICATION FAILED: File does not exist: {file_path}")
        return False
    file_size = os.path.getsize(file_path)
    if file_size < expected_min_size:
        logger.error(f"VERIFICATION FAILED: File too small ({file_size} bytes): {file_path}")
        return False
    logger.info(f"VERIFIED: {file_path} exists ({file_size} bytes)")
    return True

# Authentication
def authenticate(base_url):
    try:
        with requests.Session() as session:
            # Set the client certificate and root certificate for the session
            session.cert = (client_cert_path, client_key_path)  # Use (cert, key) if both are required
            session.verify = root_cert_path

            # Set the custom User-Agent header
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.2; '+ app_name +'; '+ app_version +') Gecko/20100101 Firefox/113.0'
            })

            response = session.get(base_url)

            # Perform the POST request for authentication
            response = session.post(base_url+'hl7pull.aspx', data={
                'Page': 'Login',
                'Mode': 'Silent',
                'UserID': user_id,
                'Password': password
            })

            # Check response status and content
            if response.status_code == 200:
                logger.debug(f"Auth response body: {response.text}")
                if '<Authentication>AccessGranted</Authentication>' in response.text:
                    # Save cookies for later use
                    cookies = session.cookies
                    logger.info("Authentication successful.")
                    return session, cookies
                else:
                    logger.info("Authentication failed.")
                    return None, None
            else:
                logger.info(f"Authentication HTTP request failed with status code {response.status_code}.")
                return None, None

    except SSLError as e:
        logger.error(f"SSL Error: {e}")
        return None, None

def query_new_results(session, base_url, cookies, pending=False):
    data = {
        'Page': 'HL7',
        'Query': 'NewRequests'
    }
    if pending:
        data['Pending'] = 'Yes'

    logger.info(f"Querying for new results with data: {data}")
    response = session.post(base_url + 'hl7pull.aspx', data=data, cookies=cookies)
    response_size = len(response.text)
    logger.info(f"Query response: HTTP {response.status_code}, body size: {response_size} chars")

    if response.status_code == 200:
        # Save raw response to disk IMMEDIATELY before any parsing
        # This ensures we never lose data even if our parsing code has a bug
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'response_{timestamp}.xml'
        file_path = os.path.join(incoming_xml_folder_path, file_name)

        try:
            with open(file_path, 'w') as file:
                file.write(response.text)
        except Exception as e:
            logger.error(f"CRITICAL: Failed to save raw response to {file_path}: {e}")
            return False

        if not verify_file_on_disk(file_path):
            logger.error(f"CRITICAL: Raw response file verification failed: {file_path}")
            return False

        logger.info(f"Raw response saved to {file_path}")

        # Log response for debugging
        logger.debug(f"Query response body (first 2000 chars): {response.text[:2000]}")

        # Parse the XML response
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML response: {e}")
            logger.error(f"Raw response saved at {file_path} for manual inspection")
            return False

        # Log the root element tag and attributes for debugging
        logger.info(f"Response root tag: '{root.tag}', attributes: {root.attrib}")

        # Log child elements for visibility
        children = list(root)
        logger.info(f"Root has {len(children)} child element(s): {[child.tag for child in children]}")

        # Find all Message elements
        messages = root.findall('.//Message')
        actual_count = len(messages)
        logger.info(f"Found {actual_count} Message element(s) in response.")

        # Extract the MessageCount from the root element
        message_count = root.get('MessageCount')
        if message_count is not None:
            # Convert message_count to integer for comparison
            try:
                message_count = int(message_count)
            except ValueError:
                logger.info("MessageCount is not a valid integer.")
                return False

            logger.info(f"MessageCount attribute: {message_count}, actual messages found: {actual_count}")

            # Verify the count
            if actual_count != message_count:
                logger.info(f"Mismatch: Expected {message_count} messages, but found {actual_count}.")
                return False
        else:
            logger.info(f"MessageCount attribute not found in the response. Found {actual_count} Message element(s) in XML.")

        if actual_count == 0:
            logger.info("No messages available for download.")
            # Clean up the empty response file - no data worth keeping
            try:
                os.remove(file_path)
                logger.debug(f"Removed empty response file: {file_path}")
            except Exception:
                pass
            return None  # None = no messages (skip ACK), False = error

        # File already saved above - now copy to mule incoming folder
        dest_path = os.path.join(incomingMuleFolder, file_name)
        try:
            shutil.copy(file_path, dest_path)
        except Exception as e:
            logger.error(f"Failed to copy file from {file_path} to {dest_path}: {e}")
            return False

        if not verify_file_on_disk(dest_path):
            logger.error(f"CRITICAL: Mule folder file verification failed: {dest_path}")
            return False

        logger.info(f"File copied to mule incoming folder: {dest_path}")
        logger.info(f"SUCCESS: Downloaded and saved {actual_count} message(s). XML: {file_path}, Mule: {dest_path}")
        return True

    else:
        logger.info(f"XML fetch HTTP request failed with status code {response.status_code}.")
        return False

def send_acknowledgement(session, base_url, cookies, positive=True):
    ack_status = 'Positive' if positive else 'Negative'
    logger.info(f"Sending {ack_status} acknowledgement...")
    response = session.post(base_url + 'hl7pull.aspx', data={
        'Page': 'HL7',
        'ACK': ack_status
    }, cookies=cookies)

    if response.status_code == 200:
        logger.debug(f"ACK response body: {response.text}")
        if '<HL7Messages/>' in response.text:
            logger.info("Acknowledgement sent.")
        elif '<HL7Messages ReturnCode="1"/>' in response.text:
            logger.info("Error processing acknowledgement.")
        elif '<HL7Messages ReturnCode="0"/>' in response.text:
            logger.info("Acknowledgement successfully processed.")
        else:
            logger.info("Unexpected response for acknowledgement.")
    else:
        logger.info(f"ACK HTTP request failed with status code {response.status_code}.")

def sign_out(session, base_url, cookies):
    response = session.post(base_url + 'hl7pull.aspx', data={
        'Logout': 'Yes'
    }, cookies=cookies)

    if response.status_code == 200:
        logger.info("Signed out successfully.")
    else:
        logger.info(f"Signout HTTP request failed with status code {response.status_code}.")

def main():

    logger.info("Script is running")

    # if is_locked():
    #     logger.info("Script is already running. Exiting.")
    #     sys.exit(1)

    # Create a lock file
    # create_lock()

    os.makedirs(incoming_HL7_folder_path, exist_ok=True)
    os.makedirs(incoming_xml_folder_path, exist_ok=True)
    os.makedirs(incomingMuleFolder, exist_ok=True)

    session, cookies = authenticate(base_url)

    if session and cookies:
        status = query_new_results(session, base_url, cookies, pending=True)

        if status is True:
            # Messages successfully downloaded and saved - mark them as received
            send_acknowledgement(session, base_url, cookies, positive=True)
            logger.info("Positive acknowledgement sent")
        elif status is None:
            # No messages available (<HL7Messages/>) - nothing to acknowledge
            logger.info("No messages to process, skipping acknowledgement.")
        else:
            # Error occurred - send negative ACK so messages remain available for retry
            # Per Excelleris docs: must always ACK after query or get blocked for 10 minutes
            send_acknowledgement(session, base_url, cookies, positive=False)
            logger.info("Negative acknowledgement sent (messages remain available for retry)")

        sign_out(session, base_url, cookies)
    else:
        logger.error("Authentication failed, cannot proceed.")

    # Ensure the lock file is removed after the script finishes
    # remove_lock()

if __name__ == "__main__":
    main()
