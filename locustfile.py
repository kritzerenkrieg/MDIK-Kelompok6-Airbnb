# locustfile.py
from locust import HttpUser, TaskSet, task, between
import random

class ListingTasks(TaskSet):
    @task(3)
    def list_default(self):
        self.client.get("/listings?page=1&limit=20")

    @task(2)
    def list_filtered(self):
        max_price = random.choice([50, 100, 200, 500])
        self.client.get(f"/listings?price_lte={max_price}")

    @task(1)
    def list_search(self):
        q = random.choice(["Historic", "Vita", "Capitol"])
        self.client.get(f"/listings?search={q}&page=1&limit=10")

class WebsiteUser(HttpUser):
    tasks = [ListingTasks]
    wait_time = between(1, 3)  # waktu tunggu acak di antara request