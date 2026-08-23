def authenticate(user):
    return jwt.encode(user.id)
