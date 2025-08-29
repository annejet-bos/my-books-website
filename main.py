from flask import Flask, render_template, redirect, url_for, request
from flask.cli import load_dotenv
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, desc
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
    star_rating: Mapped[float] = mapped_column(Float, nullable=True)
    spice_rating: Mapped[float] = mapped_column(Float, nullable=True)
    ranking: Mapped[int] = mapped_column(Integer, nullable=True)
    review: Mapped[str] = mapped_column(String(250), nullable=True)
    img_url: Mapped[str] = mapped_column(String(250), nullable=True)

with app.app_context():
    db.create_all()


class RateBookForm(FlaskForm):
    star_rating = FloatField('Your star rating out of 5 e.g. 3.5', validators=[DataRequired()])
    spice_rating = FloatField('Your spice rating out of 5 e.g. 2.5', validators = [DataRequired()])
    review = StringField('Your review', validators=[DataRequired()])
    done = SubmitField('Done')


class AddBookForm(FlaskForm):
    title = StringField('Book Title', validators=[DataRequired()])
    add = SubmitField('Add Book')


@app.route("/")
def home():
    result = db.session.execute(db.select(Book).order_by(Book.star_rating))
    all_books = result.scalars().all()
    rank = 1
    for book in all_books:
        book.ranking = rank
        rank += 1
        db.session.commit()
    all_books = db.session.execute(db.select(Book).order_by(desc(Book.ranking))).scalars()
    return render_template("index.html", books = all_books)

@app.route('/edit', methods=['GET', 'POST'])
def edit():
    form = RateBookForm()
    book_id = request.args.get('id')
    book_to_update = db.get_or_404(Book, book_id)

    if form.validate_on_submit():
        book_to_update.star_rating = float(form.star_rating.data)
        book_to_update.spice_rating = float(form.spice_rating.data)
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
        # **gebruik search API**
        response = requests.get(f"https://openlibrary.org/search.json?title={book_to_find}")
        results = response.json()['docs']

        # alleen de eerste 10 resultaten tonen
        results = results[:10]

        return render_template('select.html', results=results)
    return render_template('add.html', form=form)

@app.route('/find')
def find():
    olid = request.args.get('id')  # dit is nog steeds de index in search results of key

    if not olid:
        return redirect(url_for('home'))

    # **gebruik search result opnieuw** (of bewaar selectie id in URL)
    # Stel dat we de id doorgeven als index in de lijst van search results:
    # Voor eenvoud hier: we doen een tweede search
    response = requests.get(f"https://openlibrary.org/search.json?q={olid}")
    results = response.json()['docs']
    if not results:
        return redirect(url_for('home'))

    selected = results[0]  # pak eerste resultaat (OLID/cover_id)

    title = selected.get('title', 'No Title')
    author_name = selected.get('author_name', ['Unknown'])[0]
    year = selected.get('first_publish_year', 0)

    # **Nieuwe cover_i logica**
    cover_id = selected.get('cover_i')
    if cover_id:
        img_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"  # **gebruik cover_i**
    else:
        img_url = None  # fallback

    # Voeg toe aan DB
    new_book = Book(
        title=title,
        author=author_name,
        year=year,
        img_url=img_url
    )
    db.session.add(new_book)
    db.session.commit()

    return redirect(url_for('edit', id=new_book.id))

if __name__ == '__main__':
    app.run(debug=True)
