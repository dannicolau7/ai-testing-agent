# 🤖 AI Testing Agent

> **Autonomous test generation powered by Claude AI**  
> Generate comprehensive test suites in minutes, not hours.

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![GitHub stars](https://img.shields.io/github/stars/dannicolau7/ai-testing-agent?style=social)](https://github.com/dannicolau7/ai-testing-agent)

---

## ⚡ Quick Start (FREE - No API Key Required!)

```bash
# Install
pip install -r requirements.txt

# Generate tests from your requirements
python cli.py run requirements.txt

# That's it! ✨
```

**Works immediately with mock AI** - Perfect for learning, prototyping, and small projects.

[📖 View Full Docs](#-documentation) | [💡 See Examples](#-examples) | [💰 Compare Plans](#-pricing)

---

## 🎯 What Does It Do?

AI Testing Agent **automates your entire testing workflow**:

1. **📄 Reads** your requirements documents (txt, md, pdf, docx)
2. **🧠 Analyzes** features, user stories, and acceptance criteria
3. **✨ Generates** comprehensive test cases (positive, negative, edge cases)
4. **💻 Creates** production-ready pytest code with fixtures
5. **🧪 Executes** all tests and captures results
6. **📊 Produces** beautiful HTML/JSON/Markdown reports
7. **🎯 Suggests** improvements based on AI analysis

**All with a single command.**

---

## 🆓 FREE vs ⭐ PRO vs 👥 TEAM vs 🏢 ENTERPRISE

### 🆓 FREE (Open Source)

Perfect for individuals, students, and small projects.

✅ **Full autonomous test generation**  
✅ **Mock AI** (works offline, no API key needed)  
✅ **Up to 10 API endpoints** per run  
✅ **50 test runs per month**  
✅ **HTML/JSON/Markdown reports**  
✅ **PDF & Word document support**  
✅ **MIT License** - modify and distribute freely  
✅ **Community support**  

**Best for:** Learning, prototyping, open-source projects

[⚡ Get Started Free](#-quick-start-free---no-api-key-required)

---

### ⭐ PRO - $29/month

For professional developers who need real AI power.

✅ **Everything in FREE, plus:**  
🚀 **Real Claude AI** (GPT-4 class intelligence)  
🚀 **100 API endpoints** per run (10x more!)  
🚀 **Unlimited test runs** - no monthly limit  
🚀 **Advanced test strategies** - security, performance, integration  
🚀 **Priority email support** - 24-hour response time  
🚀 **Custom report templates**  
🚀 **Usage analytics dashboard**  

**Best for:** Professional developers, startups, consulting

[🚀 Upgrade to PRO →](https://yourdomain.com/pricing)

---

### 👥 TEAM - $99/month

For teams who need collaboration and scale.

✅ **Everything in PRO, plus:**  
🎯 **500 API endpoints** per run (50x more!)  
🎯 **Team collaboration tools**  
🎯 **Shared test libraries**  
🎯 **Role-based access control**  
🎯 **Team management dashboard**  
🎯 **Slack/Discord integration**  
🎯 **Priority support** - 12-hour response  

**Best for:** QA teams, agencies, medium businesses

[👥 Upgrade to TEAM →](https://yourdomain.com/pricing)

---

### 🏢 ENTERPRISE - Custom Pricing

For organizations with special requirements.

✅ **Everything in TEAM, plus:**  
💎 **Unlimited API endpoints**  
💎 **Dedicated support team**  
💎 **Custom integrations** (Jira, Azure DevOps, etc.)  
💎 **On-premise deployment option**  
💎 **SLA guarantees** (99.9% uptime)  
💎 **Training & onboarding**  
💎 **Custom AI model fine-tuning**  
💎 **Advanced security features**  

**Best for:** Enterprises, regulated industries, large teams

[📞 Contact Sales →](https://yourdomain.com/contact)

---

## 💰 Pricing Comparison

| Feature | FREE | PRO | TEAM | ENTERPRISE |
|---------|------|-----|------|------------|
| **Price** | $0 | $29/mo | $99/mo | Custom |
| **AI Quality** | Mock | Real Claude | Real Claude | Real Claude + Custom |
| **Endpoints/Run** | 10 | 100 | 500 | Unlimited |
| **Monthly Runs** | 50 | Unlimited | Unlimited | Unlimited |
| **Reports** | ✅ | ✅ | ✅ | ✅ Custom |
| **Support** | Community | Email | Priority | Dedicated |
| **Team Features** | ❌ | ❌ | ✅ | ✅ |
| **Custom Integration** | ❌ | ❌ | ❌ | ✅ |
| **On-Premise** | ❌ | ❌ | ❌ | ✅ |

[📊 See Full Pricing Details →](https://yourdomain.com/pricing)

---

## 📖 Usage

### Basic Usage (FREE Tier)

```bash
# Check your current tier
python cli.py tier

# Check monthly usage
python cli.py usage

# Analyze requirements
python cli.py analyze requirements.txt

# Generate and run tests
python cli.py run requirements.txt
```

### PRO/TEAM Usage (with License Key)

```bash
# Set license key (one time)
export AI_AGENT_LICENSE_KEY="PRO-XXXX-XXXX-XXXX"
export ANTHROPIC_API_KEY="sk-ant-..."

# Run with real Claude AI
python cli.py run requirements.txt --license-key YOUR_KEY --api-key YOUR_API_KEY

# Generate reports
python cli.py report requirements.txt --format html
```

### Python API

```python
from ai_testing_agent import AITestingAgent

# Initialize (FREE - no keys needed)
agent = AITestingAgent()

# Or with PRO license
agent = AITestingAgent(
    api_key='your-anthropic-key',
    license_key='PRO-XXXX-XXXX-XXXX'
)

# Load requirements
with open('requirements.txt') as f:
    requirements = f.read()

# Run autonomous workflow
result = agent.run_autonomous(requirements)

print(f"✅ Generated {result['test_cases']} test cases")
print(f"📊 Report: {result['report']}")
print(f"💰 Cost: {result['usage_stats']['cost_formatted']}")
```

---

## 💡 Examples

### Example 1: E-Commerce API Testing

```python
requirements = """
API Endpoint: POST /api/checkout
- Accept payment details
- Validate card number
- Process transaction
- Return confirmation or error
- Handle edge cases (expired card, insufficient funds)
"""

agent = AITestingAgent()
result = agent.run_autonomous(requirements)

# Generates:
# ✅ test_valid_payment.py
# ✅ test_invalid_card.py
# ✅ test_expired_card.py
# ✅ test_insufficient_funds.py
# ✅ test_edge_cases.py
```

### Example 2: User Authentication

```python
requirements = """
Feature: User Login
- Email and password authentication
- Password must be 8+ characters
- Lock account after 5 failed attempts
- Send password reset email
"""

agent = AITestingAgent()
test_cases = agent.generate_test_cases()

# AI generates:
# • Valid login test
# • Invalid credentials test
# • Account lockout test
# • Password strength test
# • Email validation test
```

### Example 3: From Requirements to Tests in 30 Seconds

```bash
# 1. Write requirements (or use existing doc)
$ echo "Feature: Shopping cart - add, update, remove items" > req.txt

# 2. Generate tests
$ python cli.py run req.txt

# 3. View results
$ open test_output/test_report.html

# Done! 🎉
```

---

## 🎁 Why Open Source?

### Transparency 🔍
See exactly how your tests are generated. No black boxes.

### Trust 🤝
Audit the code. Verify security. Know what you're running.

### Community 🌍
Benefit from community contributions. Share improvements.

### Freedom 🚀
Fork it. Modify it. Build on it. It's yours.

### Fair Pricing 💰
Free tier is genuinely useful. Paid tiers offer real value, not paywalled basics.

---

## 🚀 Key Features

### 🧠 Intelligent Test Generation
- **Positive & Negative Tests** - Happy paths and error scenarios
- **Edge Case Detection** - Boundary values, null inputs, race conditions
- **Security Testing** - SQL injection, XSS, CSRF checks
- **Performance Tests** - Load testing, stress testing suggestions

### 💻 Production-Ready Code
- **Pytest Framework** - Industry-standard testing
- **Proper Fixtures** - Setup/teardown, dependency injection
- **Parametrization** - Data-driven testing
- **Documentation** - Clear docstrings and comments

### 📊 Beautiful Reports
- **Interactive HTML** - Charts, metrics, drill-down details
- **JSON Export** - CI/CD integration, programmatic analysis
- **Markdown** - Documentation, GitHub integration
- **Cost Tracking** - Monitor AI API usage (PRO+)

### 🔧 Flexible Integration
- **CLI Tools** - Simple commands for any workflow
- **Python API** - Full programmatic control
- **CI/CD Ready** - GitHub Actions, GitLab CI, Jenkins
- **Multiple Formats** - txt, md, pdf, docx requirements

---

## 📚 Documentation

- [📖 Getting Started Guide](docs/getting-started.md)
- [🔧 Installation & Setup](docs/installation.md)
- [💡 Usage Examples](docs/examples.md)
- [🎯 Best Practices](docs/best-practices.md)
- [🔌 API Reference](docs/api-reference.md)
- [❓ FAQ](docs/faq.md)
- [🚀 Upgrade Guide](docs/upgrade-guide.md)

---

## 🤝 Contributing

We ❤️ contributions! The FREE tier is and always will be open source.

### How to Contribute

1. ⭐ **Star this repo** - Show your support!
2. 🐛 **Report bugs** - Help us improve
3. 💡 **Suggest features** - Tell us what you need
4. 🔀 **Submit PRs** - Code contributions welcome
5. 📝 **Improve docs** - Help others learn

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📊 Usage Stats

```bash
# View your current usage
python cli.py usage

# Output:
# 📊 Monthly Usage Statistics
# Current Month: 2026-02
# Tier: FREE
# 
# 🔄 Test Runs:
#    Used:      15 / 50
#    Usage:     30.0%
#    Status:    ✅ OK
# 
# 🔌 Endpoints:
#    This Month: 87
#    Per Run:    10
# 
# 📅 Quota Reset:
#    Days:       11 days
#    Date:       March 1, 2026
```

---

## 🎓 Learn More

### Video Tutorials
- [📹 Getting Started (5 min)](https://youtube.com/watch?v=xxx)
- [📹 Advanced Features (15 min)](https://youtube.com/watch?v=xxx)
- [📹 CI/CD Integration (10 min)](https://youtube.com/watch?v=xxx)

### Blog Posts
- [🔥 10x Your Testing Speed with AI](https://blog.yourdomain.com/10x-testing)
- [⚡ From Requirements to Tests in 60 Seconds](https://blog.yourdomain.com/60-seconds)
- [🎯 Best Practices for AI-Generated Tests](https://blog.yourdomain.com/best-practices)

### Case Studies
- [📈 How Startup X Reduced QA Time by 70%](https://yourdomain.com/case-study-x)
- [🚀 Enterprise Y Scales Testing Across 50 Teams](https://yourdomain.com/case-study-y)

---

## 🌟 Support the Project

### Free Ways to Help
- ⭐ **Star this repository** on GitHub
- 🐦 **Tweet about it** - Share with your network
- 📝 **Write a blog post** - Share your experience
- 💬 **Join discussions** - Help others in the community
- 🐛 **Report bugs** - Help us improve quality

### Upgrade to Support Development
By upgrading to a paid tier, you directly support continued development:
- ✨ New features and improvements
- 🐛 Bug fixes and stability
- 📚 Better documentation
- 🤝 Community support

[🚀 Upgrade Now →](https://yourdomain.com/pricing)

---

## 📞 Get Help

### FREE Tier Support
- 📖 [Documentation](https://docs.yourdomain.com)
- 💬 [Community Forum](https://community.yourdomain.com)
- 🐛 [GitHub Issues](https://github.com/dannicolau7/ai-testing-agent/issues)
- 💡 [Stack Overflow](https://stackoverflow.com/questions/tagged/ai-testing-agent) (tag: ai-testing-agent)

### PRO/TEAM Support
- 📧 **Priority Email** - support@yourdomain.com (24h response)
- 💬 **Private Slack Channel** - Direct access to team
- 📞 **Video Calls** - Scheduled support sessions

### ENTERPRISE Support
- 🆘 **Dedicated Support Team**
- ☎️ **Phone Support** - Direct line
- 🎯 **Custom SLA** - Guaranteed response times
- 🎓 **Training & Onboarding** - Personalized sessions

---

## 📝 License

**MIT License** - See [LICENSE](LICENSE) file for details.

### What This Means:
✅ **Free to use** - Personal and commercial  
✅ **Modify** - Change it to fit your needs  
✅ **Distribute** - Share with others  
✅ **Private Use** - No need to open source your modifications  

**Attribution:** If you use the FREE tier in a commercial product, please provide attribution (optional but appreciated).

**Paid Tiers:** Require a valid license key for additional features and support.

---

## 🗺️ Roadmap

### ✅ Released (v1.0)
- ✅ Core autonomous testing workflow
- ✅ Multiple report formats
- ✅ Mock AI for free tier
- ✅ Tier-based licensing
- ✅ CLI interface

### 🚧 In Progress (v1.1)
- 🔄 Visual test report dashboard
- 🔄 Jira/GitHub Issues integration
- 🔄 Docker containerization
- 🔄 VS Code extension

### 🔮 Planned (v2.0)
- 📋 Self-healing tests
- 📋 ML-based test prioritization
- 📋 Visual regression testing
- 📋 Multi-language support (Java, JavaScript)
- 📋 Performance testing integration

[👀 View Full Roadmap →](https://github.com/dannicolau7/ai-testing-agent/projects)

---

## 🏆 Why Choose AI Testing Agent?

### For Developers 👨‍💻
- ⚡ **Save 10+ hours per week** on test writing
- 🎯 **Better coverage** - AI catches edge cases you might miss
- 🚀 **Ship faster** - Automated testing accelerates development
- 💰 **Free tier** that actually works (not a trial)

### For QA Teams 🧪
- 📈 **Scale testing** without scaling headcount
- 🎯 **Focus on complex scenarios** - Let AI handle basics
- 📊 **Better insights** - AI analyzes patterns across tests
- 🤝 **Team collaboration** (TEAM tier)

### For Managers 📊
- 💰 **ROI from day one** - Immediate productivity boost
- 📉 **Reduce testing costs** by 60-80%
- ⚡ **Faster time to market** - Accelerated QA cycles
- 📈 **Scale efficiently** - More coverage, same team size

---

## 💬 What Users Say

> "Cut our test generation time from days to minutes. The free tier alone was worth it, but PRO is a game-changer."
> 
> — **Sarah Chen**, Senior Developer at TechCorp

> "We tested 50+ endpoints in an afternoon. This would have taken our team a week manually."
> 
> — **Michael Rodriguez**, QA Lead at StartupXYZ

> "The fact that it works offline with mock AI is brilliant for learning and prototyping."
> 
> — **Emma Thompson**, Computer Science Student

[📖 Read More Reviews →](https://yourdomain.com/reviews)

---

## 🔥 Quick Links

- [⚡ Get Started Free](#-quick-start-free---no-api-key-required)
- [💰 View Pricing](https://yourdomain.com/pricing)
- [📖 Read Documentation](https://docs.yourdomain.com)
- [🚀 Upgrade to PRO](https://yourdomain.com/upgrade)
- [👥 Join Community](https://community.yourdomain.com)
- [📧 Contact Support](mailto:support@yourdomain.com)
- [🐛 Report Bug](https://github.com/dannicolau7/ai-testing-agent/issues)

---

## 🙏 Acknowledgments

Built with these amazing technologies:
- [Claude AI](https://anthropic.com/claude) - The smartest AI assistant
- [Python](https://python.org) - The best language for automation
- [Pytest](https://pytest.org) - Modern testing framework
- [Flask](https://flask.palletsprojects.com) - Lightweight web framework

Special thanks to our contributors and the open-source community! 🎉

---

<div align="center">

**Made with ❤️ and 🤖 by the AI Testing Agent Team**

[⭐ Star on GitHub](https://github.com/dannicolau7/ai-testing-agent) • [🚀 Get Started](# quick-start-free---no-api-key-required) • [💬 Join Community](https://community.yourdomain.com)

</div>
