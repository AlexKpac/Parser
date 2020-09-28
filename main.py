import logging
import collections

import bs4
import requests

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('tc')

ParseResult = collections.namedtuple(
    'ParseResult',
    (
        'content'
    ),
)

class Client:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36'
            #'Accept-Language': 'ru',
        }
        self.result = []

    def load_page(self, page: int = None):
        url = 'https://www.technocity.ru/catalog/detail/754413/'
        res = self.session.get(url=url)
        res.raise_for_status()
        return res.text

    def parse_page(self, text: str):
        soup = bs4.BeautifulSoup(text, 'lxml')
        container = soup.select('p.price-normal')
        for block in container:
            self.parse_block(block=block)

    def parse_block(self, block):
        logger.info(block)
        logger.info('=' * 100)

        '''
        url_block = block.select_one('p.price-normal')
        if not url_block:
            logger.error('no url_block')
            return

        logger.info('%s', content)
'''
    def run(self):
        text = self.load_page()
        self.parse_page(text=text)


if __name__ == '__main__':
    parser = Client()
    parser.run()
