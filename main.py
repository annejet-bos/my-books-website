from flask import Flask, render_template, redirect, url_for, request
from flask.cli import load_dotenv
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, desc, Date
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, SubmitField, FloatField, DateField
from wtforms.validators import DataRequired, Optional
from dotenv import load_dotenv
from datetime import datetime, date
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

with app.app_context():
    db.create_all()


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


@app.route("/")
def home():
    # doel instellen (kun je later in DB zetten, maar voor nu hardcoded)
    goal = 50

    # tel boeken die een einddatum hebben in dit jaar
    current_year = datetime.now().year
    read_books = db.session.query(Book).filter(
        Book.date_finished.isnot(None),
        Book.date_finished.between(f"{current_year}-01-01", f"{current_year}-12-31")
    ).count()

    # percentage berekenen
    progress = int((read_books / goal) * 100) if goal > 0 else 0

    # --- Currently Reading ---
    currently_reading = db.session.query(Book).filter(
        Book.date_started.isnot(None),
        Book.date_finished.is_(None)
    ).limit(5).all()

    # --- Recently Read ---
    recently_read = db.session.query(Book).filter(
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



@app.route('/delete')
def delete():
    book_id = request.args.get('id')
    book_to_delete = db.get_or_404(Book, book_id)

    db.session.delete(book_to_delete)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete-tbr')
def delete_tbr():
    book_id = request.args.get('id')
    book_to_delete = db.get_or_404(Book, book_id)

    db.session.delete(book_to_delete)
    db.session.commit()
    return redirect(url_for('tbr'))


@app.route('/add', methods=['GET', 'POST'])
def add():
    form = AddBookForm()

    if form.validate_on_submit():
        book_to_find = form.title.data
        response = requests.get(f"https://openlibrary.org/search.json?title={book_to_find}")
        results = response.json()['docs']

        # alleen de eerste 10 resultaten tonen
        results = results[:10]

        return render_template('select.html', results=results)
    return render_template('add.html', form=form)

@app.route('/add-currently-reading', methods=['GET', 'POST'])
def add_currently_reading():
    form = AddBookForm()
    if form.validate_on_submit():
        book_to_find = form.title.data
        response = requests.get(f"https://openlibrary.org/search.json?title={book_to_find}")
        results = response.json()['docs']

        if not results:
            return redirect(url_for('home'))

        results = results[:10]

        return render_template('select_current_read.html', results = results)

    return render_template('add.html', form=form)

@app.route('/add-tbr', methods=['GET', 'POST'])
def add_tbr():
    form = AddBookForm()
    if form.validate_on_submit():
        book_to_find = form.title.data
        response = requests.get(f"https://openlibrary.org/search.json?title={book_to_find}")
        results = response.json()['docs']

        if not results:
            return redirect(url_for('home'))

        results = results[:10]

        return render_template('select_tbr.html', results = results)

    return render_template('add.html', form=form)


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


@app.route('/find')
def find():
    olid = request.args.get('id')  # dit is nog steeds de index in search results of key
    if not olid:
        return redirect(url_for('home'))


    response = requests.get(f"https://openlibrary.org/search.json?q={olid}")
    results = response.json()['docs']
    if not results:
        return redirect(url_for('home'))

    selected = results[0]  # pak eerste resultaat (OLID/cover_id)

    title = selected.get('title', 'No Title')
    author_name = selected.get('author_name', ['Unknown'])[0]
    year = selected.get('first_publish_year', 0)
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


@app.route('/find-current')
def find_current():
    olid = request.args.get('id')
    if not olid:
        return redirect(url_for('home'))

    response = requests.get(f"https://openlibrary.org/search.json?q={olid}")
    results = response.json()['docs']
    if not results:
        return redirect(url_for('home'))

    selected = results[0]

    title = selected.get('title', 'No Title')
    author_name = selected.get('author_name', ['Unknown'])[0]
    year = selected.get('first_publish_year', 0)
    cover_id = selected.get('cover_i')
    img_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None

    new_book = Book(
        title=title,
        author=author_name,
        year=year,
        img_url=img_url,
        date_started=date.today()
    )
    db.session.add(new_book)
    db.session.commit()

    return redirect(url_for('home'))


@app.route('/find-tbr')
def find_tbr():
    olid = request.args.get('id')
    if not olid:
        return redirect(url_for('tbr'))

    response = requests.get(f"https://openlibrary.org/search.json?q={olid}")
    results = response.json()['docs']
    if not results:
        return redirect(url_for('tbr'))

    selected = results[0]

    title = selected.get('title', 'No Title')
    author_name = selected.get('author_name', ['Unknown'])[0]
    year = selected.get('first_publish_year', 0)
    cover_id = selected.get('cover_i')
    img_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None

    new_book = Book(
        title=title,
        author=author_name,
        year=year,
        img_url=img_url
    )
    db.session.add(new_book)
    db.session.commit()

    return redirect(url_for('tbr'))



if __name__ == '__main__':
    app.run(debug=True)
