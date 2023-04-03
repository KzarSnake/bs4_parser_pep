import logging

from requests import RequestException

from exceptions import ParserFindTagException, RequestIsNoneException


def get_response(session, url):
    try:
        response = session.get(url)
        if response is None:
            error_msg = f'Ответ пуст'
            logging.error(error_msg, stack_info=True)
            raise RequestIsNoneException(error_msg)
        response.encoding = 'utf-8'
        return response
    except RequestException:
        logging.exception(
            f'Возникла ошибка при загрузке страницы {url}', stack_info=True
        )


def find_tag(soup, tag, attrs=None):
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag
