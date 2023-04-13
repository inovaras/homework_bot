from dotenv import load_dotenv
import json
import http
import logging
import os
import requests
import sys
import time
import telegram

from exceptions import (
    BadStatusException,
    BadAPIAnswerError,
    NetworkError,
    ServerError
)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
TOKEN_NAMES = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens():
    """Проверить переменные окружения."""
    has_missing_tokens = False
    for name in TOKEN_NAMES:
        if not globals()[name]:
            has_missing_tokens = True
            logger.critical(
                f'Отсутствует обязательная переменная окружения бота: {name}'
            )
    if has_missing_tokens:
        sys.exit()


def send_message(bot, message):
    """Отправить сообщение в Телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Удачная отправка сообщения в Telegram')
    except telegram.TelegramError as e:
        logger.error(f'Сбой при отправке сообщения в Telegram: {e}')


def get_api_answer(timestamp):
    """Получить ответ от API Yandex."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException as e:
        raise NetworkError(f'Проблема с получением ответа: {e}')
    try:
        api_answer = response.json()
    except json.JSONDecodeError as e:
        raise BadAPIAnswerError(f'Ошибка при конвертировании в json: {e}')
    if response.status_code != http.HTTPStatus.OK:
        if api_answer.keys() == {'error', 'code'}:
            raise ServerError(
                f'Ошибка {api_answer["error"]}, {api_answer["code"]}',
                response.status_code
            )
        raise BadStatusException(
            f'Ошибка {response.text}', response.status_code
        )

    logger.debug('Получен ответ от сервера :)')
    return api_answer


def check_response(response):
    """Проверить ответ API на соответствие документации."""
    if type(response) is not dict:
        raise TypeError(f'Ответ от сервера не словарь, а {type(response)}')

    if 'homeworks' not in response:
        raise BadAPIAnswerError("В словаре нет ключа 'homeworks'")

    if 'current_date' not in response:
        raise BadAPIAnswerError("В словаре нет ключа 'current_date'")

    if type(response['homeworks']) is not list:
        raise TypeError("Тип значений по ключу 'homeworks' не список")


def parse_status(homework):
    """Извлечь информацию о домашке."""
    if 'status' not in homework:
        raise BadAPIAnswerError('Нет ключа "status" в ответе')

    if 'homework_name' not in homework:
        raise BadAPIAnswerError('Нет ключа "homework_name" в ответе')

    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise BadAPIAnswerError(f'Получен неожиданный статус {status}')

    verdict = HOMEWORK_VERDICTS[status]
    homework_name = homework['homework_name']

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            api_response = get_api_answer(timestamp)
            check_response(api_response)
            homeworks = api_response['homeworks']
            if homeworks:
                logger.debug('Обнаружено новое обновление')
                status = parse_status(homeworks[0])
                send_message(bot, status)
            else:
                logger.debug('Нет новых обновлений')
            timestamp = api_response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
