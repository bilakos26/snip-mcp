interface User {
    id: number;
    name: string;
    email: string;
}

type Status = "active" | "inactive";

enum Color {
    Red = "RED",
    Green = "GREEN",
    Blue = "BLUE",
}

function greetUser(user: User): string {
    return `Hello, ${user.name}!`;
}

class UserService {
    private users: User[] = [];

    addUser(user: User): void {
        this.users.push(user);
    }

    getUser(id: number): User | undefined {
        return this.users.find(u => u.id === id);
    }
}
