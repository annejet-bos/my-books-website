from flask import Flask, render_template, redirect, url_for, request
from flask.cli import load_dotenv
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, SubmitField, FloatField
from wtforms.validators import DataRequired
from dotenv import load_dotenv
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
    rating: Mapped[float] = mapped_column(Float, nullable=True)
    ranking: Mapped[int] = mapped_column(Integer, nullable=True)
    review: Mapped[str] = mapped_column(String(250), nullable=True)
    img_url: Mapped[str] = mapped_column(String(250), nullable=True)

with app.app_context():
    db.create_all()


class RateBookForm(FlaskForm):
    rating = FloatField('Your rating out of 10 e.g. 7.5', validators=[DataRequired()])
    review = StringField('Your review', validators=[DataRequired()])
    done = SubmitField('Done')


class AddBookForm(FlaskForm):
    title = StringField('Book Title', validators=[DataRequired()])
    add = SubmitField('Add Book')


@app.route("/")
def home():
    result = db.session.execute(db.select(Book).order_by(Book.rating.desc()))
    all_books = result.scalars().all()
    rank = 1
    for book in all_books:
        book.ranking = rank
        rank += 1
        db.session.commit()
    all_books = db.session.execute(db.select(Book).order_by(Book.ranking.desc())).scalars()
    return render_template("index.html", books = all_books)

@app.route('/edit', methods=['GET', 'POST'])
def edit():
    form = RateBookForm()
    book_id = request.args.get('id')
    book_to_update = db.get_or_404(Book, book_id)

    if form.validate_on_submit():
        book_to_update.rating = float(form.rating.data)
        book_to_update.review = form.review.data
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('edit.html', form=form, book=book_to_update)


@app.route('/delete')
def delete():
    book_id = request.args.get('id')
    book_to_delete = db.get_or_404(Book, book_id)

    db.session.delete(book_to_delete)
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/add', methods=['GET', 'POST'])
def add():
    form = AddBookForm()

    if form.validate_on_submit():
        book_to_find = form.title.data
        url = f"https://openlibrary.org/search.json?title={book_to_find}"
        response = requests.get(url)
        data = response.json()
        results = data.get('docs', [])
        return render_template('select.html', results = results)
    return render_template('add.html', form=form)


@app.route('/find')
def find():
    olid = request.args.get('id')  # Open Library Work ID

    if not olid:
        # Geen ID → terug naar home (of errorpagina)
        return redirect(url_for('home'))

    DETAILS_URL = f"https://openlibrary.org/works/{olid}.json"
    response = requests.get(DETAILS_URL)

    if response.status_code != 200:
        return f"Kon geen details vinden voor werk-ID {olid}", 404

    results = response.json()

    # Auteur ophalen
    author_name = "Unknown"
    if "authors" in results and results["authors"]:
        author_key = results["authors"][0]["author"]["key"]
        author_data = requests.get(f"https://openlibrary.org{author_key}.json").json()
        author_name = author_data.get("name", "Unknown")

    # Jaar uit created veld halen
    year = 0
    if "created" in results and "value" in results["created"]:
        year = int(results["created"]["value"][:4])

    new_book = Book(
        title=results.get('title', 'No Title'),
        author=author_name,
        year=year,
        img_url=f"https://covers.openlibrary.org/b/olid/{olid}-L.jpg"
    )
    db.session.add(new_book)
    db.session.commit()

    return redirect(url_for('edit', id=new_book.id))

if __name__ == '__main__':
    app.run(debug=True)
