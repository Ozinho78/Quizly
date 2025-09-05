# Backend Project for Coderr-App with Django REST Framework (DRF)

This project is the backend for the **Coderr Freelancer Platform**, built with Django and Django REST Framework (DRF).  
It provides APIs for user management, offers, orders, reviews, and profiles of both customers and business users.  
The backend connects to a given frontend (JS-based) and exposes all required REST endpoints.

-------------------------------------------------------------------------------------------------------------

## Features

- **User Authentication & Registration**
  - Token-based authentication
  - Two profile types: `customer` and `business`
  - Custom validators for email and password strength
- **Profiles**
  - Business and customer profiles with full details
  - Endpoints to fetch all business or customer profiles
- **Offers**
  - Business users can create, update, delete and list offers
  - Offer details with pricing models (basic, standard, premium)
- **Orders**
  - Customers can place orders on offers
  - Endpoints to track in-progress, completed, pending, and delivered orders
  - Count endpoints: `order-count/{business_user_id}/` and `completed-order-count/{business_user_id}/`
- **Reviews**
  - Customers can leave reviews for business users
  - One review per customer per business
- **Base Info**
  - Aggregated platform statistics (review count, average rating, business user count, offer count)

-------------------------------------------------------------------------------------------------------------

## Technology Stack

- [Django](https://www.djangoproject.com/) 5.x
- [Django REST Framework](https://www.django-rest-framework.org/)
- [SQLite](https://www.sqlite.org/) (default database)
- Token Authentication
- CORS enabled (for frontend integration)

-------------------------------------------------------------------------------------------------------------

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/Ozinho78/Coderr
cd Coderr
```


### 2. Create a virtual environment
```bash
python -m venv env
```
##### Windows:
```bash
env\Scripts\activate
```
##### macOS/Linux:
```bash
source env/bin/activate
```


### 3. Install dependencies
```bash
pip install -r requirements.txt
```


### 4. Run database migrations
```bash
python manage.py migrate
```


### 5. Creating a superuser
```bash
python manage.py createsuperuser
```


### 6. Run the server
``` bash
python manage.py runserver
```

### The API will be available at:
http://127.0.0.1:8000/api/


### Example Endpoints
POST /api/registration/ → Register new user <br>
POST /api/login/ → Login and get token <br>
GET /api/profiles/business/ → List all business profiles <br>
GET /api/offers/ → List all offers <br>
POST /api/orders/ → Create a new order <br>
GET /api/reviews/ → List all reviews <br>
POST /api/reviews/ → Create a review (customer only) <br>
GET /api/base-info/ → Get platform statistics <br>
<br>
<br>
<br>