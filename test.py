import requests


book_title = input('What book do you want to add? ')
URL = f'https://openlibrary.org/search.json?title={book_title}'


response = requests.get(URL)
results = response.json()
print(results)