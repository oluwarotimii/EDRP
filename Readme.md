Great! Below is the updated `README.md` with a **Usage** section that includes examples for using the API with `curl`, `HTTPie`, and `Python (requests)`.

---

```markdown
# 📚 School ERP API

A RESTful API for managing a School ERP (Enterprise Resource Planning) system. It supports user authentication, school onboarding, department management, and more.

---

## 🧾 Overview

- **Version:** 1.0.0  
- **Specification:** OpenAPI 3.1.0  
- **Base URL:** `/api/`

---

## 📌 Features

- User registration and authentication
- Password management
- School registration and administration
- Department and class management
- Secure token-based access control

---

## 🔐 Authentication

Authentication is handled using **OAuth2 Password Bearer Tokens**.

Include this in the request header for protected routes:

```

Authorization: Bearer \<access\_token>

````

---

## 🔑 Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register a new user |
| `/auth/login` | POST | Authenticate and obtain token |
| `/auth/change-password` | POST | Change current user password |
| `/auth/me` | GET | Get authenticated user profile |

---

## 🏫 School Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/schools` | POST | Register a new school |
| `/schools` | GET | Get all schools (admin only) |
| `/schools/{id}` | GET | Get school by ID |
| `/schools/{id}` | PUT | Update school info (admin only) |

---

## 🧱 Example Usage

### 🔒 Login (Get Access Token)

#### curl

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user@example.com", "password": "yourpassword"}'
````

#### HTTPie

```bash
http POST http://localhost:8000/api/auth/login username=user@example.com password=yourpassword
```

#### Python (requests)

```python
import requests

url = "http://localhost:8000/api/auth/login"
data = {"username": "user@example.com", "password": "yourpassword"}
res = requests.post(url, json=data)

token = res.json().get("access_token")
print("Access Token:", token)
```

---

### 🏫 Register a School

```bash
curl -X POST http://localhost:8000/api/schools \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "school_name": "Springfield High",
    "admin_email": "admin@springfield.edu",
    "admin_password": "strongpassword123"
  }'
```

---

### 📥 Create a Department

```bash
curl -X POST http://localhost:8000/api/departments \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Science",
    "school_id": 1
  }'
```

---

## 📄 Common Response Codes

* `200 OK` – Request was successful.
* `201 Created` – Resource successfully created.
* `401 Unauthorized` – Invalid or missing token.
* `422 Unprocessable Entity` – Validation or input error.

---

## 🧰 Tech Stack

* FastAPI
* OAuth2 (Password Flow)
* JSON over HTTP
* OpenAPI 3.1 for schema documentation

---

## 📬 Contact

For support, contributions, or integration help, please contact the project maintainer.

---

## 📄 License

This API is proprietary. All rights reserved.

```

---

Let me know if you want a section on **Environment Setup**, **API Testing with Postman**, or **Contribution Guidelines**.
```
