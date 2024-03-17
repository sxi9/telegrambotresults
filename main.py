import logging
import os
import requests
from bs4 import BeautifulSoup
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
TOKEN = os.getenv('TELEGRAM_TOKEN')
BASE_URL = "http://103.42.86.148"
FORM_URL = f"{BASE_URL}/jazz3/index.php"

# Initialize bot
bot = Bot(TOKEN)


def start(update: Update, context: CallbackContext) -> None:
  """Sends a message when the command /start is issued."""
  message = 'Hi! Send me your roll number to get your results.\n\n'
  message += 'This bot was created by [Samurai Sastha](https://www.instagram.com/samurai_sastha/). Give a follow!'
  update.message.reply_markdown(message)


def get_csrf_token(session):
  """Fetch the CSRF token required for the POST request."""
  response = session.get(FORM_URL)
  soup = BeautifulSoup(response.text, 'html.parser')
  csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
  return csrf_token


def fetch_pdfs(session, roll_no):
  """Fetch PDF links from the website."""
  csrf_token = get_csrf_token(session)
  data = {'csrf_token': csrf_token, 'rollno': roll_no, 'Results': 'Results'}
  headers = {'Content-Type': 'application/x-www-form-urlencoded'}
  response = session.post(FORM_URL, data=data, headers=headers)
  soup = BeautifulSoup(response.content, 'html.parser')
  pdf_links = [link.get('href') for link in soup.select('a[href$=".pdf"]')]
  return pdf_links


def make_absolute_url(relative_path):
  """Correctly form the absolute URL from a relative path."""
  corrected_path = relative_path.replace('../', '/')  # Correcting path
  return f"{BASE_URL}{corrected_path}"


def send_pdf_directly(update, pdf_url):
  """Attempt to download and send the PDF directly if the URL is not accepted."""
  try:
    response = requests.get(pdf_url, stream=True)
    # Deduce filename from URL or generate a generic one if impossible
    filename = pdf_url.split('/')[-1] if '/' in pdf_url else "document.pdf"
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
      shutil.copyfileobj(response.raw, tmp_file)
      tmp_file.seek(0)
      update.message.reply_document(document=open(tmp_file.name, 'rb'),
                                    filename=filename)
  except Exception as e:
    logger.error(f"Error in downloading or sending the PDF directly: {e}")
    update.message.reply_text(
        "Failed to download or send the PDF. Please try again.")


def roll_number(update: Update, context: CallbackContext) -> None:
  """Process roll number and send PDFs."""
  session = requests.Session()
  roll_no = update.message.text.strip()
  pdf_links = fetch_pdfs(session, roll_no)

  if pdf_links:
    for link in pdf_links:
      absolute_url = make_absolute_url(link)
      logger.info(f"Attempting to send PDF URL: {absolute_url}")
      try:
        update.message.reply_document(document=absolute_url)
      except Exception as e:
        logger.error(f"Error sending PDF: {e}, URL: {absolute_url}")
        # Attempting direct download and send as a fallback
        logger.info(
            f"Attempting direct download and send for URL: {absolute_url}")
        send_pdf_directly(update, absolute_url)
  else:
    update.message.reply_text("No results found for your roll number.")


def error(update: Update, context: CallbackContext):
  """Log Errors caused by Updates."""
  logger.warning('Update "%s" caused error "%s"', update, context.error)


def main() -> None:
  """Start the bot."""
  updater = Updater(TOKEN, use_context=True)
  dp = updater.dispatcher

  dp.add_handler(CommandHandler("start", start))
  dp.add_handler(MessageHandler(Filters.text & ~Filters.command, roll_number))
  dp.add_error_handler(error)

  updater.start_polling()
  updater.idle()


if __name__ == '__main__':
  main()
