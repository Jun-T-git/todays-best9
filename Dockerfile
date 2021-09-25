FROM python:3.6
RUN mkdir /app
WORKDIR /app
COPY ./app /app
RUN pip install -r requirements.txt
CMD ["python", "tweet_todays_best9.py"]