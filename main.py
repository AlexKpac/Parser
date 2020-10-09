from selenium import webdriver
from lxml import html

page_num = 1
url = 'https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/?p={}&i=1&mode=list&brand=brand-apple'.format(page_num)

driver = webdriver.Chrome(executable_path=r'C:\Py_Projects\ParserOnlineShop\venv\WebDriverManager\chrome\85.0.4183.87\chromedriver_win32\chromedriver.exe')
driver.get(url)

content = driver.page_source
tree = html.fromstring(content)

print(tree.xpath('//div[@class="n-catalog-product__info"]')[0].attrib)

#last_page = tree.xpath('//span[@class=" item edge"]')[0].attrib.get('data-page-number')
#print(last_page)