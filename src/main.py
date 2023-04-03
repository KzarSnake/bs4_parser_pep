import logging
import re

from urllib.parse import urljoin

import requests_cache

from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL, PEP_URL
from exceptions import ParserFindTagException
from outputs import control_output
from utils import find_tag, get_response


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = main_div.find(
        'div', attrs={'class': 'toctree-wrapper compound'}
    )
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )
    result = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python, desc='progress bar'):
        version_a_tag = find_tag(section, 'a')
        url = version_a_tag['href']
        full_url = urljoin(whats_new_url, url)
        response = get_response(session, full_url)
        soup = BeautifulSoup(response.text, features='lxml')
        tag_h1 = find_tag(soup, 'h1')
        tag_dl = find_tag(soup, 'dl')
        dl_text = tag_dl.text.replace('\n', ' ')
        result.append((full_url, tag_h1.text, dl_text))
    return result


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    logging.info('Сбор последних версий начат!')
    soup = BeautifulSoup(response.text, features='lxml')
    sidebar = soup.find(name='div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all(name='ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise ParserFindTagException('Ничего не найдено!')
    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in tqdm(a_tags):
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        version, status = text_match.groups() if text_match else a_tag.text, ''
        results.append((link, version, status))
    logging.info('Сбор последних версий закончен!')
    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    soup = BeautifulSoup(response.text, 'lxml')

    main_tag = soup.find('div', {'role': 'main'})
    table_tag = main_tag.find('table', {'class': 'docutils'})
    pdf_a4_tag = table_tag.find('a', {'href': re.compile(r'.+pdf-a4\.zip$')})

    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)

    filename = archive_url.split('/')[-1]

    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    response = session.get(archive_url)

    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    response = get_response(session, PEP_URL)
    soup = BeautifulSoup(response.text, 'lxml')
    div_section = find_tag(soup, 'section', attrs={'id': 'numerical-index'})
    tr_rows = BeautifulSoup.find_all(div_section, 'tr')

    count_status = {}
    total_peps = 0
    results = [('Статус', 'Количество')]

    for tr_row in tqdm(tr_rows[1:]):
        total_peps += 1
        data = list(find_tag(tr_row, 'abbr').text)
        preview_status = data[1:][0] if len(data) > 1 else ''
        url = urljoin(
            PEP_URL,
            find_tag(tr_row, 'a', attrs={'class': 'pep reference internal'})[
                'href'
            ],
        )
        response_next = get_response(session, url)
        soup_next = BeautifulSoup(response_next.text, 'lxml')
        table_info = find_tag(
            soup_next, 'dl', attrs={'class': 'rfc2822 field-list simple'}
        )
        status_pep_page = (
            table_info.find(string='Status')
            .parent.find_next_sibling('dd')
            .string
        )
        if status_pep_page in count_status:
            count_status[status_pep_page] += 1
        if status_pep_page not in count_status:
            count_status[status_pep_page] = 1
        if status_pep_page not in EXPECTED_STATUS[preview_status]:
            error_message = (
                'Несовпадающие статусы:\n'
                f'{url}\n'
                f'Статус в карточке: {status_pep_page}\n'
                'Ожидаемые статусы: '
                f'{EXPECTED_STATUS[preview_status]}'
            )
            logging.warning(error_message)
    for status in count_status:
        results.append((status, count_status[status]))
    results.append(('Total', total_peps))
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
