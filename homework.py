import datetime
import logging
import os
import sys
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import time
import json

from dotenv import load_dotenv
import telegram
from exceptions import BadStatusException, BadAPIAnswerError, NetworkError



load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    '''Проверить переменные окружения'''
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Отсутствуют обязательные переменные окружения во время запуска бота')
        exit()


def send_message(bot, message):
    '''Отправить сообщение в Телеграмм'''
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Удачная отправка сообщения в Telegram')
    except Exception as e:
        logger.error(f'Сбой при отправке сообщения в Telegram: {e}')


def get_api_answer(timestamp):
    '''Получить ответ от API Yandex'''
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers= HEADERS, params=payload)
    except Exception as e:
        raise NetworkError(f'Проблема с получением ответа: {e}')
    if response.status_code != HTTPStatus.OK:
        raise BadStatusException(f'Статус: {response.status_code}')
    try:
        api_answer = response.json()
    except json.JSONDecodeError as e:
        raise BadAPIAnswerError(f'Ошибка при конвертировании в json: {e}')
    logger.debug('Получен ответ от сервера :)')
    return api_answer


def check_response(response):
    '''Проверить ответ API на соответствие документации'''
    if type(response) is not dict:
        raise TypeError(f'Ответ от сервера не словарь, а {type(response)}')

    if 'homeworks' not in response:
        raise BadAPIAnswerError("В словаре нет ключа 'homeworks'")

    if 'current_date' not in response:
        raise BadAPIAnswerError("В словаре нет ключа 'current_date'")

    if type(response['homeworks']) is not list:
        raise TypeError("Тип значений по ключу 'homeworks' не список")


def parse_status(homework):
    '''Извлечь информацию о домашке'''
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

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()


