# 🚀 SessionMaster

Advanced Telegram Session Management Bot with comprehensive features for power users.

## ✨ Features

### 🔐 Session Management
- **Multi-session support** - Manage up to 10 Telegram accounts
- **Session validation** - Automatic session health checks
- **Secure storage** - Encrypted session data
- **Session analytics** - Track usage and performance

### 📱 Advanced Operations
- **Bulk messaging** - Send messages to multiple recipients
- **Channel management** - Subscribe/unsubscribe from channels
- **Contact operations** - Export/import contacts in multiple formats
- **Dialog cleanup** - Remove channels, groups, bots, or private chats
- **Member extraction** - Get member lists from channels/groups

### 🤖 Automation
- **Message scheduling** - Schedule messages for later delivery
- **Auto-reply system** - Automatic responses to incoming messages
- **Keyword monitoring** - Monitor channels for specific keywords
- **Inactive group cleanup** - Automatically leave inactive groups

### 📊 Analytics & Reporting
- **Usage statistics** - Comprehensive activity tracking
- **Performance metrics** - Monitor API usage and limits
- **Export reports** - Generate detailed usage reports
- **Real-time dashboard** - Web-based monitoring interface

### 🌐 Web Interface
- **Modern dashboard** - Clean, responsive web interface
- **REST API** - Full API access for integrations
- **Real-time updates** - Live session monitoring
- **Bulk operations** - Web-based bulk tools

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-repo/SessionMaster.git
   cd SessionMaster
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

5. **Start web interface** (optional)
   ```bash
   python web_interface.py
   ```

## ⚙️ Configuration

### Required Settings
- `API_ID` - Your Telegram API ID
- `API_HASH` - Your Telegram API Hash
- `BOT_TOKEN` - Your bot token from @BotFather

### Optional Settings
- `ENCRYPTION_KEY` - 32-character key for data encryption
- `MAX_SESSIONS` - Maximum sessions per user (default: 10)
- `RATE_LIMIT` - API rate limit per minute (default: 30)
- `WEBHOOK_URL` - Webhook URL for notifications
- `PROXY_URL` - Proxy server URL

## 🚀 Usage

### Bot Commands
- `/start` - Main menu and session selection
- `/help` - Show available commands
- `/stats` - View your usage statistics
- `/templates` - Manage message templates
- `/web` - Web interface information

### Web Dashboard
Access the web dashboard at `http://localhost:5000` for advanced features:
- Session management
- Bulk operations
- Analytics and reporting
- Export/import tools

## 🔧 Advanced Features

### Message Templates
Save frequently used messages as templates for quick access.

### Scheduled Messages
Schedule messages to be sent at specific times.

### Bulk Operations
- Send messages to multiple recipients
- Subscribe to multiple channels
- Export contacts from multiple sessions

### Analytics
- Track message sending statistics
- Monitor channel subscription activity
- View session usage patterns
- Generate detailed reports

## 🛡️ Security Features

- **Input sanitization** - Prevents log injection attacks
- **Path validation** - Prevents directory traversal
- **Rate limiting** - Protects against abuse
- **Secure file handling** - Safe file operations
- **Data encryption** - Encrypted sensitive data storage

## 📁 Project Structure

```
SessionMaster/
├── bot.py                 # Main bot application
├── config.py             # Configuration management
├── database.py           # Database operations
├── session_manager.py    # Core session functions
├── session_operations.py # Advanced session operations
├── scheduler.py          # Message scheduling system
├── analytics.py          # Analytics and reporting
├── web_interface.py      # Web dashboard
├── utils.py              # Utility functions
├── exceptions.py         # Custom exceptions
├── templates/            # Web templates
├── sessions/             # Session files storage
├── temp/                 # Temporary files
├── TData/               # TData exports
└── logs/                # Log files
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is for educational and legitimate use only. Users are responsible for complying with Telegram's Terms of Service and applicable laws.

## 🆘 Support

- **Telegram:** @worpli
- **Issues:** GitHub Issues
- **Documentation:** Wiki

## 🔄 Updates

- **v2.0** - Complete rewrite with advanced features
- **v1.0** - Initial release

---

Made with ❤️ by @worpli