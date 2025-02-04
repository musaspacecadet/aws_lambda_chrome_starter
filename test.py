import requests
import json
import base64
import gzip
import os

def test_lambda_invocation(urls):
    """
    Tests the Lambda function invocation, decodes the response data, and saves the HTML files.

    Args:
        urls (list): A list of URLs to be processed by the Lambda function.

    Returns:
        dict: The response from the Lambda function invocation.
    """

    url = "http://localhost:9000/2015-03-31/functions/function/invocations"
    headers = {'Content-Type': 'application/json'}
    data = {'urls': urls}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None

def decode_and_save_html(url_mappings, output_dir="output_html"):
    """
    Decodes the base64-encoded, gzipped HTML content and saves the files.

    Args:
        url_mappings (dict): The URL mappings from the Lambda response.
        output_dir (str): The directory to save the HTML files.
    """

    os.makedirs(output_dir, exist_ok=True)

    for url, data in url_mappings.items():
        filename = data.get('filename')
        encoded_content = data.get('content')

        if filename and encoded_content:
            try:
                # Decode from base64
                decoded_content = base64.b64decode(encoded_content)
                # Decompress using gzip
                decompressed_content = gzip.decompress(decoded_content).decode('utf-8')

                # Sanitize filename (remove invalid characters)
                safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
                filepath = os.path.join(output_dir, safe_filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(decompressed_content)

                print(f"Saved HTML for {url} to {filepath}")
            except Exception as e:
                print(f"Error decoding or saving HTML for {url}: {e}")
        else:
            print(f"Missing filename or content for {url}")

if __name__ == "__main__":
    test_urls = ["http://example.com", "http://google.org", "https://github.com"]
    result = test_lambda_invocation(test_urls)

    if result:
        print("Lambda invocation successful!")
        url_mappings = result.get("body")
        if url_mappings:
            # Parse the JSON string in 'body'
            url_mappings = json.loads(url_mappings).get("url_mappings", {})
            decode_and_save_html(url_mappings)
        else:
            print("No URL mappings found in the response.")
    else:
        print("Lambda invocation failed.")