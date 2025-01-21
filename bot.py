import os
import logging
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from database import get_db, get_movie_by_stream_id, search_movies, increment_movie_views, create_movie
from datetime import datetime, timedelta
from config import Config
import secrets
import time
from aiohttp import web
import aiohttp
import json

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_shortener_apis():
    """Check if URL shortener APIs are working."""
    async with aiohttp.ClientSession() as session:
        # Check Get2Short API
        if Config.GET2SHORT_API_KEY:
            try:
                url = "https://get2short.com/api/create"
                data = {
                    "api_key": Config.GET2SHORT_API_KEY,
                    "url": "https://example.com"
                }
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info("Get2Short API is working")
                    else:
                        logger.error(f"Get2Short API error: {await response.text()}")
            except Exception as e:
                logger.error(f"Get2Short API check failed: {e}")

        # Check ModijiURL API
        if Config.MODIJIURL_API_KEY:
            try:
                url = "https://modijiurl.com/api/create"
                data = {
                    "api_key": Config.MODIJIURL_API_KEY,
                    "url": "https://example.com"
                }
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info("ModijiURL API is working")
                    else:
                        logger.error(f"ModijiURL API error: {await response.text()}")
            except Exception as e:
                logger.error(f"ModijiURL API check failed: {e}")

async def check_heroku_status():
    """Check if Heroku account is active."""
    try:
        heroku_api_key = os.getenv('HEROKU_API_KEY')
        if not heroku_api_key:
            logger.warning("HEROKU_API_KEY not set, skipping Heroku status check")
            return

        async with aiohttp.ClientSession() as session:
            headers = {
                'Accept': 'application/vnd.heroku+json; version=3',
                'Authorization': f'Bearer {heroku_api_key}'
            }
            async with session.get('https://api.heroku.com/account', headers=headers) as response:
                if response.status == 200:
                    logger.info("Heroku account is active")
                else:
                    logger.error(f"Heroku account check failed: {await response.text()}")
    except Exception as e:
        logger.error(f"Error checking Heroku status: {e}")

async def batch_command(update: Update, context: CallbackContext) -> None:
    """Handle batch upload command for admins."""
    try:
        user_id = update.effective_user.id
        if user_id not in Config.ADMINS:
            await update.message.reply_text("⚠️ This command is only for admins!")
            return

        # Check if files were provided
        if not context.args:
            await update.message.reply_text(
                "📝 Usage: /batch title1|url1 title2|url2 ...\n\n"
                "Example: /batch 'Movie 1|http://example.com/movie1.mp4' 'Movie 2|http://example.com/movie2.mp4'"
            )
            return

        status_message = await update.message.reply_text("🔄 Processing batch upload...")
        
        success_count = 0
        failed_count = 0
        results = []

        for arg in context.args:
            try:
                # Split title and URL
                if '|' not in arg:
                    results.append(f"❌ Invalid format: {arg}")
                    failed_count += 1
                    continue

                title, file_url = arg.split('|', 1)
                
                # Create movie entry
                movie = await create_movie(
                    title=title.strip(),
                    stream_id=secrets.token_hex(8),
                    file_url=file_url.strip(),
                    uploader_id=str(user_id)
                )
                
                results.append(f"✅ Added: {title}")
                success_count += 1
                
            except Exception as e:
                results.append(f"❌ Error adding {title}: {str(e)}")
                failed_count += 1

        # Send results
        result_text = "📊 Batch Upload Results:\n\n"
        result_text += f"✅ Successfully added: {success_count}\n"
        result_text += f"❌ Failed: {failed_count}\n\n"
        result_text += "\n".join(results)

        await status_message.edit_text(result_text)

    except Exception as e:
        logger.error(f"Error in batch command: {e}")
        await update.message.reply_text("❌ An error occurred during batch upload.")

async def start(update: Update, context: CallbackContext) -> None:
    """Handle /start command."""
    # [Previous start command code remains the same]

async def web_app():
    """Create web app for Heroku."""
    app = web.Application()
    return app

async def main():
    """Start the bot."""
    try:
        # Check APIs and Heroku status
        await check_shortener_apis()
        await check_heroku_status()

        # Initialize bot application
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("batch", batch_command))
        
        # Get port from environment variable
        port = int(os.environ.get('PORT', '8443'))
        
        # Start web app
        webapp = await web_app()
        runner = web.AppRunner(webapp)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"Web app is listening on port {port}")
        
        # Start the bot
        await application.initialize()
        await application.start()
        await application.run_polling()
        
        logger.info("Bot started successfully!")
        
        # Keep the app running
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    asyncio.run(main())