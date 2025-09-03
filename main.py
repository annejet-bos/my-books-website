from flask import Flask, render_template, redirect, url_for, request
from flask.cli import load_dotenv
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy import Integer, String, Float, desc, Date
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, SubmitField, FloatField, DateField
from wtforms.validators import DataRequired, Optional
from dotenv import load_dotenv
from datetime import datetime, date
from collections import Counter
import requests
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
Bootstrap5(app)
CSRFProtect(app)

# CREATE DB
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///books.db"

# Create the extension
db = SQLAlchemy(model_class=Base)

# Initialise the app with the extension
db.init_app(app)


# CREATE TABLE
class Book(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable = False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    star_rating: Mapped[float] = mapped_column(Float, nullable=True)
    spice_rating: Mapped[float] = mapped_column(Float, nullable=True)
    ranking: Mapped[int] = mapped_column(Integer, nullable=True)
    review: Mapped[str] = mapped_column(String(250), nullable=True)
    img_url: Mapped[str] = mapped_column(String(250), nullable=True)
    date_started: Mapped[datetime] = mapped_column(Date, nullable = True)
    date_finished: Mapped[datetime] = mapped_column(Date, nullable = True)
    pages: Mapped[int] = mapped_column(Integer, nullable=True)
    genre: Mapped[str] = mapped_column(String(100), nullable=True)

with app.app_context():
    db.create_all()


# --------------------------------------------- FORMS -------------------------------------------------------
class RateBookForm(FlaskForm):
    star_rating = FloatField('Your star rating out of 5 e.g. 3.5', validators=[DataRequired()])
    spice_rating = FloatField('Your spice rating out of 5 e.g. 2.5', validators = [DataRequired()])
    review = StringField('Your review', validators=[DataRequired()])
    date_started = DateField('Date Started', format = '%Y-%m-%d', validators = [Optional()])
    date_finished = DateField('Date Finished', format='%Y-%m-%d', validators=[Optional()])
    done = SubmitField('Done')


class AddBookForm(FlaskForm):
    title = StringField('Book Title', validators=[DataRequired()])
    add = SubmitField('Add Book')


# ------------------------------------------------- HELPERS -------------------------------------------------
def search_openlibrary(query, limit=10):
    """Search books via OpenLibrary and return docs."""
    response = requests.get(f"https://openlibrary.org/search.json?q={query}")
    results = response.json().get("docs", [])
    return results[:limit]


def get_book_details(work_key):
    """Get additional book details from OpenLibrary work API."""
    try:
        if work_key.startswith('/works/'):
            work_key = work_key[7:]

        response = requests.get(f"https://openlibrary.org/works/{work_key}.json")
        if response.status_code == 200:
            work_data = response.json()

            # Extract and categorize genres
            raw_subjects = work_data.get('subjects', [])
            genre = categorize_genre(raw_subjects)

            return {
                'genre': genre,
                'raw_subjects': raw_subjects[:5]  # Keep first 5 for debugging
            }
    except Exception as e:
        print(f"Error fetching work details: {e}")

    return {'genre': None, 'raw_subjects': []}


def get_book_pages_from_editions(edition_keys, median_pages=None):
    """Try multiple editions to find page count."""
    if edition_keys:
        # Try first few editions (avoid overloading the API)
        for edition_key in edition_keys[:3]:
            try:
                if edition_key.startswith('/books/'):
                    edition_key = edition_key[7:]

                response = requests.get(f"https://openlibrary.org/books/{edition_key}.json")
                if response.status_code == 200:
                    edition_data = response.json()
                    pages = edition_data.get('number_of_pages')

                    # Ensure it's a positive integer
                    if pages and isinstance(pages, (int, float)) and pages > 0:
                        return int(pages)
            except Exception:
                continue  # ignore errors and try next edition

    # Fallback: use median pages from search result
    if median_pages and isinstance(median_pages, (int, float)) and median_pages > 0:
        return int(median_pages)

    return None


def get_edition_details(edition_key):
    """Get page count from a specific edition."""
    try:
        if edition_key.startswith('/books/'):
            edition_key = edition_key[7:]  # Remove '/books/' prefix

        response = requests.get(f"https://openlibrary.org/books/{edition_key}.json")
        if response.status_code == 200:
            edition_data = response.json()
            return edition_data.get('number_of_pages')
    except:
        pass
    return None


def book_from_result(result, started=False):
    """Make a Book object out of an OpenLibrary result with better page/genre detection."""
    title = result.get('title', 'No Title')
    author_name = result.get('author_name', ['Unknown'])[0]
    year = result.get('first_publish_year', 0)
    cover_id = result.get('cover_i')
    img_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None

    # Try multiple methods to get page count
    pages = None

    # Method 1: Direct from search result
    pages = result.get('number_of_pages_median')

    # Method 2: Try from editions if no median
    if not pages:
        edition_keys = result.get('edition_key', [])
        pages = get_book_pages_from_editions(edition_keys)

    # Method 3: Try from first edition in result
    if not pages and result.get('edition_count', 0) > 0:
        if 'edition_key' in result and result['edition_key']:
            pages = get_book_pages_from_editions([result['edition_key'][0]])

    # Get genre from work details
    genre = None
    if result.get('key'):
        work_details = get_book_details(result['key'])
        genre = work_details['genre']

    return Book(
        title=title,
        author=author_name,
        year=year,
        img_url=img_url,
        pages=pages,
        genre=genre,
        date_started=date.today() if started else None
    )


def categorize_genre(raw_subjects):
    """Convert OpenLibrary's specific subjects to general genres."""
    if not raw_subjects:
        return None

    # Convert to lowercase for matching
    subjects_lower = [subject.lower() for subject in raw_subjects]
    subjects_text = ' '.join(subjects_lower)

    # Genre mapping - order matters (more specific first)
    genre_mapping = {
        'Romance': [
            'romance', 'love story', 'romantic', 'love', 'relationships',
            'contemporary romance', 'historical romance'
        ],
        'Fantasy': [
            'fantasy', 'magic', 'magical', 'dragons', 'wizards', 'elves',
            'sword and sorcery', 'epic fantasy', 'urban fantasy', 'paranormal'
        ],
        'Science Fiction': [
            'science fiction', 'sci-fi', 'space', 'aliens', 'future',
            'dystopian', 'cyberpunk', 'time travel', 'robots'
        ],
        'Mystery': [
            'mystery', 'detective', 'crime', 'murder', 'investigation',
            'police', 'thriller', 'suspense', 'noir'
        ],
        'Horror': [
            'horror', 'scary', 'ghost', 'vampire', 'zombie', 'supernatural',
            'gothic', 'occult'
        ],
        'Historical Fiction': [
            'historical fiction', 'historical', 'world war', 'civil war',
            'medieval', 'victorian', 'ancient'
        ],
        'Young Adult': [
            'young adult', 'ya', 'teen', 'coming of age', 'high school',
            'teenage', 'adolescent'
        ],
        'Biography': [
            'biography', 'autobiography', 'memoir', 'life story'
        ],
        'Self-Help': [
            'self-help', 'personal development', 'motivation', 'psychology',
            'business', 'productivity', 'success'
        ],
        'Non-Fiction': [
            'non-fiction', 'history', 'politics', 'science', 'nature',
            'travel', 'cooking', 'health', 'religion', 'philosophy'
        ],
        'Literary Fiction': [
            'literary fiction', 'literature', 'classic', 'literary'
        ],
        'Adventure': [
            'adventure', 'action', 'survival', 'expedition'
        ],
        'Children': [
            'children', 'juvenile', 'picture book', 'kids'
        ]
    }

    # Check each genre category
    for genre, keywords in genre_mapping.items():
        for keyword in keywords:
            if keyword in subjects_text:
                return genre

    # If no match found, return the first subject (cleaned up)
    if raw_subjects:
        first_subject = raw_subjects[0]
        # Clean up the subject
        cleaned = first_subject.replace('_', ' ').title()
        return cleaned if len(cleaned) < 20 else 'Fiction'

    return 'Fiction'


# -------------------------------------------------- ROUTES ------------------------------------------------------
@app.route("/")
def home():
    goal = 50
    current_year = datetime.now().year

    read_books = Book.query.filter(
        Book.date_finished.isnot(None),
        Book.date_finished.between(f"{current_year}-01-01", f"{current_year}-12-31")
    ).count()

    progress = int((read_books / goal) * 100) if goal > 0 else 0

    currently_reading = Book.query.filter(
        Book.date_started.isnot(None),
        Book.date_finished.is_(None)
    ).limit(5).all()

    recently_read = Book.query.filter(
        Book.date_finished.isnot(None)
    ).order_by(Book.date_finished.desc()).limit(5).all()

    return render_template(
        "home.html",
        goal=goal,
        read_books=read_books,
        progress=progress,
        currently_reading=currently_reading,
        recently_read=recently_read
    )


@app.route("/top-books")
def top_books():
    read_books = db.session.query(Book).filter(Book.date_finished.isnot(None)).order_by(desc(Book.star_rating)).all()
    for rank, book in enumerate(read_books, start=1):
        book.ranking = rank
    db.session.commit()
    return render_template("index.html", books = read_books)


@app.route('/tbr')
def tbr():
    tbr_books = db.session.query(Book).filter(
        Book.date_started.is_(None),
        Book.date_finished.is_(None)
    ).all()
    return render_template('tbr.html', books=tbr_books)


@app.route('/edit', methods=['GET', 'POST'])
def edit():
    form = RateBookForm()
    book_id = request.args.get('id')
    book_to_update = db.get_or_404(Book, book_id)

    if form.validate_on_submit():
        book_to_update.star_rating = float(form.star_rating.data)
        book_to_update.spice_rating = float(form.spice_rating.data)
        book_to_update.review = form.review.data
        book_to_update.date_started = form.date_started.data
        book_to_update.date_finished = form.date_finished.data
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('edit.html', form=form, book=book_to_update)


@app.route("/delete/<string:target>")
def delete(target):
    book_id = request.args.get('id')
    book = db.get_or_404(Book, book_id)
    db.session.delete(book)
    db.session.commit()
    return redirect(url_for('tbr' if target == "tbr" else 'home'))


@app.route("/add", methods=['GET', 'POST'])
def add():
    form = AddBookForm()
    target = request.args.get('target', None)
    if form.validate_on_submit():
        results = search_openlibrary(form.title.data)
        if not results:
            return redirect(url_for('home'))
        return render_template("select.html", results=results, target=target)
    return render_template("add.html", form=form, target=target)


@app.route('/tbr-to-cr', methods=['GET', 'POST'])
def tbr_to_cr():
    olid = request.args.get('id')
    book = db.session.get(Book, olid)
    book.date_started = date.today()
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/finish/<int:id>', methods=['GET', 'POST'])
def finish(id):
    book = db.get_or_404(Book, id)
    form = RateBookForm(
        star_rating=book.star_rating,
        spice_rating=book.spice_rating,
        review=book.review,
        date_started=book.date_started,
        date_finished=book.date_finished
    )

    if form.validate_on_submit():
        book.star_rating = form.star_rating.data
        book.spice_rating = form.spice_rating.data
        book.review = form.review.data
        book.date_started = form.date_started.data
        book.date_finished = form.date_finished.data
        db.session.commit()
        return redirect(url_for('home'))

    return render_template('finish.html', form=form, book=book)


@app.route("/find/<string:target>")
def find(target):
    olid = request.args.get('id')
    if not olid:
        return redirect(url_for('home'))

    results = search_openlibrary(olid, limit=1)
    if not results:
        return redirect(url_for('home'))

    selected = results[0]
    book = book_from_result(selected, started=(target == "current"))
    db.session.add(book)
    db.session.commit()

    if target == "current":
        return redirect(url_for('home'))
    elif target == "tbr":
        return redirect(url_for('tbr'))
    elif target == 'rate':
        return redirect(url_for('edit', id=book.id))
    else:
        return redirect(url_for('edit', id=book.id))


@app.route('/stats')
def stats():
    goal = 50
    current_year = datetime.now().year

    # Get all finished books for stats
    finished_books = Book.query.filter(Book.date_finished.isnot(None)).all()

    # Convert to JSON for JavaScript
    books_data = []
    for book in finished_books:
        books_data.append({
            'title': book.title,
            'author': book.author,
            'year': book.year,
            'star_rating': float(book.star_rating) if book.star_rating is not None else None,
            'spice_rating': float(book.spice_rating) if book.spice_rating is not None else None,
            'ranking': book.ranking,
            'review': book.review,
            'img_url': book.img_url,
            'date_started': book.date_started.isoformat() if book.date_started else None,
            'date_finished': book.date_finished.isoformat() if book.date_finished else None,
            'pages': int(book.pages) if book.pages else None,
            'genre': book.genre
        })

    read_books = Book.query.filter(
        Book.date_finished.isnot(None),
        Book.date_finished.between(f"{current_year}-01-01", f"{current_year}-12-31")
    ).count()

    progress = int((read_books / goal) * 100) if goal > 0 else 0

    return render_template('stats.html',
                           goal=goal,
                           read_books=read_books,
                           progress=progress,
                           books_data=books_data)


@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = db.get_or_404(Book, book_id)

    # Probeer description op te halen via OpenLibrary API
    description = None
    if book.genre is None or True:  # altijd proberen als je wilt
        if hasattr(book, 'work_key') and book.work_key:
            try:
                work_key = book.work_key
                if work_key.startswith('/works/'):
                    work_key = work_key[7:]
                response = requests.get(f"https://openlibrary.org/works/{work_key}.json")
                if response.status_code == 200:
                    work_data = response.json()
                    if isinstance(work_data.get('description'), dict):
                        description = work_data['description'].get('value')
                    else:
                        description = work_data.get('description')
            except:
                description = None

    return render_template('book_detail.html', book=book, description=description)



if __name__ == '__main__':
    app.run(debug=True)
