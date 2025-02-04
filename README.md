# AWS Lambda Chrome Batch Download Starter

A starter kit for running GUI mode Chrome on AWS Lambda to batch download web pages using a Chrome extension. Saves downloaded HTML with compressed content storage.

## Features

- 🚀 headfulChrome automation in AWS Lambda
- 📦 Chrome extension integration (SingleFile format)
- 🔄 Fuzzy matching of URLs to downloaded files
- 🗜️ Gzip compression + Base64 encoding of content
- 📁 Atomic file operations with proper cleanup
- 🐳 Dockerized Lambda environment

## Prerequisites

- AWS Account with Lambda access
- Docker installed locally
- Python 3.10+
- AWS CLI configured

## Installation

1. Clone repository:
```bash
git clone https://github.com/yourusername/musaspacecadet-aws_lambda_chrome_starter.git
cd musaspacecadet-aws_lambda_chrome_starter
```

2. Build Docker image:
```bash
docker build -t lambda-chrome-batch .
```

3. Install Python requirements:
```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables in `app.py`:
```python
os.environ['DOWNLOAD_DIR'] = '/tmp/snapshots'  # Lambda writable dir
os.environ['EXTENSION_DIR'] = '/tmp/unpacked_extension'
```

## Local Testing

1. Start Lambda runtime interface emulator:
```bash
docker run -p 9000:8080 lambda-chrome-batch
```

2. In another terminal, run test script:
```bash
python test.py
```

3. Check generated HTML files in `output_html/` directory

## Deployment

1. Create ECR repository in AWS
2. Push Docker image:
```bash
aws ecr get-login-password | docker login --username AWS --password-stdin YOUR_ECR_URL
docker tag lambda-chrome-batch:latest YOUR_ECR_URI/lambda-chrome-batch:latest
docker push YOUR_ECR_URI/lambda-chrome-batch:latest
```

3. Create Lambda function using container image

## Usage

Lambda event format:
```json
{
  "urls": [
    "https://example.com",
    "https://github.com",
    "https://google.com"
  ]
}
```

Sample response:
```json
{
  "url_mappings": {
    "https://example.com": {
      "filename": "d18c3abb...html",
      "content": "H4sIAAAAAAAEAI2S227j..."
    }
  }
}
```

## Customization

1. **Timeout Settings**: Adjust `max_wait_time` in `main()`
2. **Extension**: Modify `mpiodijhokgodhhofbcjdecpffjipkle.crx`
3. **Matching Logic**: Tune thresholds in `FileMatcher` class
4. **Compression**: Modify gzip/b64 encoding in `get_url_mapping_with_content()`

## Troubleshooting

**Common Issues:**
- ⏱️ Timeouts: Increase Lambda timeout/memory settings
- 🔒 File Permissions: Ensure /tmp directory write access
- 🖥️ headfulIssues: Test with visible browser first
- 🔍 Content Matching: Adjust fuzzy match thresholds

**Debugging Tips:**
1. Check CloudWatch logs
2. Test locally with `test.py`
3. Inspect downloaded files in `/tmp/snapshots`
4. Enable verbose Chrome logging via `--enable-logging=stderr`

## License

MIT License - See [LICENSE](LICENSE) for details

## Contributions

PRs welcome! Please:
1. Open issue first for major changes
2. Update tests accordingly
3. Maintain coding style consistency

Happy scraping! 🕷️  

---  
*Disclaimer: Always scrape responsibly and respect websites’ terms of service and robots.txt files.*
