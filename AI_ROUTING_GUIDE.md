# AI Routing System Documentation

## Overview

The AI Testing Agent now features intelligent routing between mock AI and real Claude API based on subscription tier and configuration. This ensures users on free tiers get immediate value while paid users benefit from advanced AI capabilities.

---

## 🎯 Features Implemented

### 1. **Tier-Based Routing**
- **Free Tier**: Automatically uses mock AI responses
- **Pro/Team/Enterprise Tiers**: Uses real Claude API when configured
- **Graceful Fallback**: Falls back to mock if API key is missing or API fails

### 2. **Enhanced _call_ai() Method**

The main routing logic intelligently directs calls:

```python
def _call_ai(self, prompt: str) -> str:
    # Free tier → Mock AI
    if self.tier == 'free':
        print("ℹ️  Using mock AI (Free tier)")
        print("💡 Upgrade to Pro for real Claude AI: https://yourdomain.com/pricing")
        return self._mock_ai_response(prompt)
    
    # Paid tiers → Real API (with fallback)
    if self.tier in ['pro', 'team', 'enterprise']:
        if not self.api_key:
            # Show clear error with instructions
            return self._mock_ai_response(prompt)
        
        try:
            return self._call_claude_api(prompt)
        except Exception as e:
            print(f"⚠️  API error: {str(e)[:100]}. Using mock fallback.")
            return self._mock_ai_response(prompt)
```

### 3. **Robust _call_claude_api() with Retry Logic**

**Features:**
- ✅ 3 automatic retry attempts
- ✅ Exponential backoff (1s, 2s, 4s)
- ✅ Rate limit handling with dynamic wait times
- ✅ Usage tracking (tokens, cost estimation)
- ✅ Comprehensive error messages

**Error Handling:**
- **Authentication Errors**: Clear instructions for fixing API key issues
- **Rate Limits**: Automatic retry with exponential backoff
- **Network Issues**: Retry logic with connection status
- **Server Errors (500/503)**: Retry with status updates
- **Client Errors (4xx)**: No retry, clear error messages

**Usage Tracking:**
```python
# Tracks automatically:
- API calls count
- Tokens used (input + output)
- Estimated cost (Claude 3.5 Sonnet pricing)
  • Input: $3 per million tokens
  • Output: $15 per million tokens
```

### 4. **Realistic Mock AI Responses**

**Enhancements:**
- ✅ **Variety**: Responses change across multiple calls
- ✅ **Context-Aware**: Different responses for different prompt types
- ✅ **Structured Data**: JSON format matching real API responses
- ✅ **Clear Labeling**: All mock responses marked with `_mock_response: True`

**Supported Prompt Types:**
1. **Requirements Parsing** → Feature lists, user stories, edge cases
2. **Test Case Generation** → Structured test case objects
3. **Pytest Code** → Executable pytest code templates
4. **Analysis** → Test coverage analysis and recommendations

---

## 🚀 Usage Examples

### Example 1: Free Tier User

```python
from ai_testing_agent import AITestingAgent

# No API key needed for free tier
agent = AITestingAgent()

# Automatically uses mock AI
response = agent._call_ai("Generate test cases for login")

# Output:
# ℹ️  Using mock AI (Free tier)
# 💡 Upgrade to Pro for real Claude AI: https://yourdomain.com/pricing
# 🎭 Generating mock AI response...
```

### Example 2: Pro Tier with API Key

```python
import os
from ai_testing_agent import AITestingAgent

# Set API key
os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-your-key-here'

# Create Pro tier agent (with valid license)
agent = AITestingAgent(license_key='your-pro-license-key')

# Uses real Claude API
response = agent._call_ai("Generate comprehensive test cases")

# Output:
# 🔄 API call attempt 1/3...
# ✅ Using real Claude AI
# 📊 Tokens: 245 in / 892 out
# 💰 Cost: $0.0141 (Total: $0.0141)
```

### Example 3: Pro Tier without API Key

```python
from ai_testing_agent import AITestingAgent

# Pro license but no API key
agent = AITestingAgent(license_key='your-pro-license-key')

# Shows helpful error, falls back to mock
response = agent._call_ai("Analyze test results")

# Output:
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ❌ ERROR: No API Key Found (PRO Tier)
# ╚══════════════════════════════════════════════════════════════════════╝
# 
# You're on the PRO tier, but no Anthropic API key is configured.
# 
# 🔧 To fix this, set your API key using one of these methods:
# ...
```

---

## 🔧 Configuration

### Setting Up the API Key

**Method 1: Environment Variable (Recommended)**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

**Method 2: Constructor Parameter**
```python
agent = AITestingAgent(api_key="sk-ant-your-key-here")
```

**Method 3: .env File**
```bash
# Create .env file in project root
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env
```

### Getting an API Key

1. Visit: https://console.anthropic.com/account/keys
2. Sign up or log in
3. Create a new API key
4. Copy and save securely

---

## 📊 Error Messages

### No API Key (Paid Tier)
```
╔══════════════════════════════════════════════════════════════════════╗
║  ❌ ERROR: No API Key Found (PRO Tier)
╚══════════════════════════════════════════════════════════════════════╝

Set ANTHROPIC_API_KEY environment variable
```

### Rate Limit Hit
```
⏱️  Rate limit reached. Retrying in 30 seconds...

Consider upgrading your Anthropic API tier:
→ https://console.anthropic.com/settings/plans
```

### API Connection Error
```
🌐 Connection error: Failed to connect
⏱️  Retrying in 2 seconds...

Check your internet connection and try again.
If the problem persists, check Anthropic status:
→ https://status.anthropic.com
```

### Authentication Error
```
❌ Authentication failed: Invalid API key

Please check your API key and try again:
1. Verify key at: https://console.anthropic.com/account/keys
2. Ensure key starts with 'sk-ant-'
3. Check for extra spaces or typos
```

---

## 🧪 Testing

Run the comprehensive test suite:

```bash
python test_ai_routing.py
```

**Tests Include:**
1. ✅ Free tier routing (mock AI)
2. ✅ Paid tier routing (real API)
3. ✅ Mock response variety
4. ✅ Usage tracking
5. ✅ Error handling and fallbacks

---

## 💡 Best Practices

### For Free Tier Users
- Mock responses provide basic functionality
- Great for testing workflow and integration
- Upgrade to Pro for production-quality AI

### For Paid Tier Users
- Always set ANTHROPIC_API_KEY
- Monitor usage tracking for cost management
- Use `.env` files to keep keys secure
- Never commit API keys to version control

### Error Handling
- System automatically falls back to mock on API errors
- Retry logic handles transient failures
- Clear error messages guide users to solutions

---

## 📈 Usage Tracking

The system tracks:

```python
agent.state['usage'] = {
    'api_calls': 0,        # Number of API calls made
    'tokens_used': 0,      # Total tokens (input + output)
    'estimated_cost': 0.0  # Estimated cost in USD
}
```

**Access Usage Data:**
```python
usage = agent.state['usage']
print(f"API Calls: {usage['api_calls']}")
print(f"Tokens Used: {usage['tokens_used']}")
print(f"Estimated Cost: ${usage['estimated_cost']:.4f}")
```

---

## 🔄 Mock Response Details

### Response Structure
All mock responses include:
```python
{
    '_mock_response': True,
    '_note': 'This is a simplified mock response...',
    # ... actual response data
}
```

### Variety Mechanism
- Responses change based on call count
- Different data sets rotated
- Random variations for realism
- Clearly labeled as mock

### Limitations
- Limited intelligence compared to real AI
- Generic recommendations
- Cannot analyze complex patterns
- Basic coverage analysis only

---

## 🆙 Upgrade Benefits

### Why Upgrade to Pro?

**Real AI Advantages:**
- 🧠 Advanced intelligence and context awareness
- 🎯 Production-quality test generation
- 📊 Deep analysis and insights
- 🔍 Complex pattern detection
- ⚡ Unlimited test runs
- 📈 100+ API endpoints
- 🛟 Priority support

**Pricing:**
Visit: https://yourdomain.com/pricing

---

## 🐛 Troubleshooting

### Mock responses instead of real AI?
1. Check tier: `print(agent.tier)`
2. Verify API key: `print(os.getenv('ANTHROPIC_API_KEY'))`
3. Check anthropic library: `pip install anthropic`

### Rate limits?
1. Wait for retry countdown
2. Check Anthropic dashboard for limits
3. Consider upgrading API tier

### Authentication errors?
1. Verify key at https://console.anthropic.com/account/keys
2. Ensure no extra spaces in key
3. Check key starts with `sk-ant-`

---

## 📚 Additional Resources

- **Anthropic Documentation**: https://docs.anthropic.com/claude/reference/getting-started
- **API Reference**: https://docs.anthropic.com/claude/reference/messages
- **Error Reference**: https://docs.anthropic.com/claude/reference/errors
- **Status Page**: https://status.anthropic.com
- **Pricing**: https://yourdomain.com/pricing

---

## ✅ Summary

The AI routing system provides:
1. ✅ Seamless tier-based routing
2. ✅ Robust error handling with retries
3. ✅ Realistic mock responses
4. ✅ Usage tracking and cost estimation
5. ✅ Clear, actionable error messages
6. ✅ Graceful fallbacks for reliability

**Result**: Users get immediate value on free tier, with smooth upgrade path to advanced AI capabilities.
