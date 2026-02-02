# Integration Plan: Colab Notebook HITL Workflow

## Overview

Integrate patterns from the Colab notebook (`SASA_workshop_2_hitl.ipynb`) into the existing TrustStackSocial project, focusing on:
1. Feedback collection for rejections
2. Improved async handling
3. Colab-compatible execution

## Key Features from Notebook

1. **Feedback Collection**: After rejection, bot asks for reason and stores it
2. **Async Patterns**: Uses async/await for better concurrency
3. **State Management**: Uses asyncio.Event for waiting on decisions
4. **Error Handling**: Handles conflicts when multiple bot instances run

## Implementation Steps

### 1. Add Feedback Collection to Telegram Bot Server

Update `telegram_bot_server.py`:
- Add `MessageHandler` to capture text feedback
- Track state: which pending post is waiting for feedback
- Store feedback in `PostApproval.notes` field
- Update message after feedback is received

### 2. Fix File Handling in Telegram Bot

Update `src/telegram_bot.py`:
- Use context managers for file operations
- Properly close files after sending media
- Handle file paths correctly

### 3. Create Colab-Compatible Script

Create `notebooks/colab_hitl_workflow.py`:
- Standalone script that can run in Colab
- Uses async patterns from notebook
- Can be imported and used in Colab cells
- Integrates with existing project modules

### 4. Add Feedback State Management

Enhance `src/database.py` or create state manager:
- Track which posts are waiting for feedback
- Store feedback collection state
- Clean up state after feedback received

## Files to Modify

1. `telegram_bot_server.py` - Add feedback collection handler
2. `src/telegram_bot.py` - Fix file handling
3. `src/approval_workflow.py` - Add feedback request method

## Files to Create

1. `notebooks/colab_hitl_workflow.py` - Colab-compatible script
2. `notebooks/README.md` - Usage instructions

## Implementation Details

### Feedback Collection Flow

```
User clicks "Reject" 
  → Bot asks "Please reply with reason"
  → User sends text message
  → Bot stores reason in PostApproval.notes
  → Bot confirms feedback received
  → Complete rejection workflow
```

### State Management

Use a simple dictionary or database to track:
- `pending_post_id` → waiting for feedback (True/False)
- Store in memory or database table

### File Handling Fix

```python
# Current (problematic - files not closed)
media = open(image_path, 'rb')

# Fixed (use context manager)
with open(image_path, 'rb') as f:
    media = f.read()
    # or use file object directly if API supports it
```

## Testing

- Test feedback collection flow end-to-end
- Test file handling with multiple images
- Test Colab script in actual Colab environment
- Verify no file handle leaks
