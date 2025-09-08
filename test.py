import requests
GOOGLE_API_KEY = 'AIzaSyDYvAQp1W6g8Hxni5l5JzxN7ABD-nP4QjA'

query = f"intitle:{'deep end'}+inauthor:{'ali hazelwood'}"

response = requests.get(
    "https://www.googleapis.com/books/v1/volumes",
    params={"q": query, "maxResults": 1, 'key': GOOGLE_API_KEY}
)
print(response.text)