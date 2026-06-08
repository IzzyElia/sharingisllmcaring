from restapi import auth, storage

if __name__ == '__main__':
    user = auth.add_user("test", "test2", ["admin"])
    print(f"Password Check {'Passed' if auth.check_password(user, "test") else 'Failed'}")
    storage.save_serializable_object(user)
    users = list(storage.load_all_objects_of_category("user", auth.User))
    deserialized_user = users[5]
    print(f"Post-Deserialization Password Check {'Passed' if auth.check_password(deserialized_user, "test") else 'Failed'}")


