"""
Tests for JD Bot
"""

import pytest
from bot import JDBot

def test_bot_initialization():
    """Test bot initialization"""
    bot = JDBot()
    assert bot.name == "JD Bot"

def test_bot_start(capsys):
    """Test bot start method"""
    bot = JDBot()
    bot.start()
    captured = capsys.readouterr()
    assert "JD Bot is starting up..." in captured.out

def test_bot_stop(capsys):
    """Test bot stop method"""
    bot = JDBot()
    bot.stop()
    captured = capsys.readouterr()
    assert "JD Bot is shutting down..." in captured.out 