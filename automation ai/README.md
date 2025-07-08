# Enhanced LinkedIn Easy Apply Bot

A robust, state-machine-driven LinkedIn Easy Apply bot using Playwright + OpenAI with enhanced error handling, pre-filled field detection, and timeout mechanisms.

## Features

### ✅ Enhanced Capabilities
- **Pre-filled Field Detection**: Checks if fields are already filled before attempting to fill them
- **Robust Modal Navigation**: Handles "Next", "Review", and "Submit" buttons with multiple selector fallbacks
- **Graceful Error Handling**: Continues operation when Easy Apply buttons are missing or broken
- **Smart GPT Fallbacks**: Provides context-aware fallback answers when GPT fails or times out
- **Infinite Loop Prevention**: Implements timeout mechanisms and duplicate state detection
- **Continuous Operation**: Can apply to n jobs without breaking on individual failures

### 🔧 Technical Improvements
- **Multiple Selector Fallbacks**: Uses multiple CSS selectors for better reliability
- **Retry Logic**: Implements exponential backoff for GPT API calls
- **State Tracking**: Prevents getting stuck in duplicate modal states
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Timeout Protection**: Configurable timeouts for modal processing

## Setup

1. **Install Dependencies**:
   ```bash
   pip install playwright openai python-dotenv python-docx
   playwright install chromium
   ```

2. **Configure Environment**:
   ```bash
   cp .env.template .env
   # Edit .env with your credentials
   ```

3. **Prepare Resume**:
   - Save your resume as a .docx file
   - Update the `RESUME_PATH` in your .env file

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LINKEDIN_EMAIL` | Your LinkedIn email | Required |
| `LINKEDIN_PASSWORD` | Your LinkedIn password | Required |
| `OPENAI_API_KEY` | Your OpenAI API key | Required |
| `RESUME_PATH` | Path to your .docx resume | Required |
| `MAX_APPLIES` | Maximum applications per session | 5 |
| `CSV_PATH` | Output CSV file path | applications.csv |
| `MODAL_TIMEOUT` | Modal processing timeout (seconds) | 300 |

## Usage

### Basic Usage
```bash
python linkedin_easy_apply_improved.py
```

### Testing Field Detection
```bash
python test_field_detection.py
```

## Key Improvements

### 1. Pre-filled Field Detection
```python
def is_field_empty(field: Locator) -> bool:
    """Check if a field is empty or contains only whitespace"""
    try:
        current_value = field.input_value() or ""
        return current_value.strip() == ""
    except Exception:
        return True
```

### 2. Smart GPT Fallbacks
```python
def get_smart_fallback(question: str) -> str:
    """Provide context-aware fallback answers based on question content"""
    q_lower = question.lower()
    
    if any(word in q_lower for word in ["year", "experience", "salary", "number"]):
        return "0"
    elif any(word in q_lower for word in ["authorized", "eligible", "legal"]):
        return "Yes"
    # ... more context-aware logic
```

### 3. Modal State Tracking
```python
def get_modal_state(modal: Locator) -> str:
    """Get a string representation of the current modal state for loop detection"""
    # Combines header text and button text to create unique state identifier
```

### 4. Multiple Selector Fallbacks
```python
def find_easy_apply_button(page: Page) -> Optional[Locator]:
    """Find Easy Apply button with multiple selector fallbacks"""
    selectors = [
        "button[data-control-name='jobdetails_topcard_inapply']",
        "button:has-text('Easy Apply')",
        "button[aria-label*='Easy Apply']",
        ".jobs-apply-button",
        # ... more fallback selectors
    ]
```

## Output

The bot generates a CSV file with the following columns:
- **Title**: Job title
- **Company**: Company name
- **Link**: Job posting URL
- **DateApplied**: Application timestamp
- **Runtime**: Time taken for application
- **Status**: Success/Incomplete status

## Error Handling

### Graceful Degradation
- Continues processing when individual jobs fail
- Skips jobs without Easy Apply buttons
- Handles modal timeouts gracefully
- Provides fallback answers when GPT fails

### Logging
- Comprehensive logging for debugging
- Warning messages for skipped jobs
- Error tracking for failed operations
- Success confirmation for completed applications

## Safety Features

### Rate Limiting
- Human-like pauses between actions
- Randomized timing to avoid detection
- Configurable delays

### Loop Prevention
- Maximum loop count limits
- Duplicate state detection
- Configurable timeouts
- Automatic modal escape mechanisms

## Troubleshooting

### Common Issues

1. **LinkedIn Checkpoint**: The bot will pause and wait for manual intervention if LinkedIn requires additional verification.

2. **GPT API Errors**: The bot uses smart fallbacks and retry logic to handle API failures gracefully.

3. **Modal Timeouts**: If a modal takes too long to process, the bot will timeout and move to the next job.

4. **Missing Easy Apply**: Jobs without Easy Apply buttons are automatically skipped.

### Debug Mode
Enable detailed logging by setting the logging level to DEBUG in the script.

## Testing

The included test script (`test_field_detection.py`) validates:
- Field detection logic
- Modal state tracking
- Form processing behavior

Run tests before using the bot to ensure everything works correctly.

## Legal and Ethical Considerations

- Use responsibly and in accordance with LinkedIn's Terms of Service
- Respect rate limits and avoid aggressive automation
- Ensure your applications are genuine and relevant
- Monitor the bot's behavior and intervene if necessary

## Support

For issues or questions:
1. Check the logs for error messages
2. Run the test script to validate functionality
3. Ensure all dependencies are properly installed
4. Verify your .env configuration is correct
