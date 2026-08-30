# Classes, Objects, State, and Methods

## Purpose

This checkpoint records the Python object-oriented programming mental model established before moving deeper into encapsulation and related mechanisms.

The emphasis is on understanding how Python objects hold state and expose behavior, rather than memorizing class syntax.

## 1. Class vs object

A class is a model/blueprint that defines what an object can contain and what behavior it can provide.

An object (instance) is a concrete instance created from that class.

```python
class Book:
    pass

book1 = Book()
book2 = Book()
```

`Book` is the class. `book1` and `book2` are separate objects. One class can produce many independent objects.

## 2. Instance attributes are object state

Attributes created through `self` in `__init__` belong to each individual instance.

```python
class Book:
    def __init__(self, title, author, price):
        self.title = title
        self.author = author
        self.price = price
```

For two objects:

```text
book1
 ├── title  -> "Python"
 ├── author -> "Guido"
 └── price  -> 8000

book2
 ├── title  -> "SIE"
 ├── author -> "Subir"
 └── price  -> 5000
```

The attribute name can be the same while the state is different because each object is a separate identity.

Changing an instance attribute on one object does not change the corresponding attribute on another object.

## 3. `__init__` initializes instance state

`__init__` is a method used during object creation to initialize the instance's state.

The class itself does not automatically have `title`, `author`, or `price` merely because those names appear as parameters of `__init__`.

This:

```python
self.price = price
```

creates `price` on the particular instance represented by `self`.

Therefore:

```python
book1.price       # instance attribute; valid
Book.price        # not defined by the class in this example
```

## 4. Methods represent behavior

A function defined inside a class is an instance method when it operates on an instance through `self`.

```python
class Book:
    def increase_price(self, amount):
        self.price = self.price + amount
```

The method is defined once on the class, but it can operate on many objects.

```python
book1.increase_price(500)
book2.increase_price(500)
```

The same behavior is reused with different object state.

## 5. What `self` means

`self` is the conventional name for the instance parameter. It refers to the current object on which the method is operating.

Conceptually:

```python
book1.describe()
```

can be understood approximately as:

```python
Book.describe(book1)
```

So inside the method:

```text
self -> book1
```

When `book2.describe()` is called:

```text
self -> book2
```

The same method therefore works against the state of whichever object called it.

## 6. Methods can mutate state or return information

A method may change the object's state:

```python
def increase_price(self, amount):
    self.price = self.price + amount
```

Or it may read the state and return a result without changing the object:

```python
def get_price_with_discount(self, discount):
    return self.price - (self.price * discount / 100)
```

The distinction is:

```text
Mutating method:
object state -> method -> changed object state

Non-mutating/query method:
object state -> method -> returned result
```

If the result is assigned to another variable:

```python
discounted = book1.get_price_with_discount(10)
```

`discounted` refers to the returned result. It does not modify `book1.price` unless the code explicitly assigns the result back to that attribute.

## 7. Object references and immutable integers

When an expression such as:

```python
self.price = self.price + amount
```

is evaluated, the right-hand side produces a new integer value/object because integers are immutable. The assignment then makes `self.price` refer to that result.

The old integer becomes eligible for garbage collection only if no other references to it remain.

The precise mental model is therefore:

```text
attribute -> reference to an object
assignment -> changes what the attribute references
immutable int -> cannot be modified in place
```

## 8. Instance attributes vs class attributes

An attribute defined directly in the class body is a class attribute:

```python
class Book:
    category = "Programming"
```

An attribute assigned through `self` is an instance attribute:

```python
class Book:
    def __init__(self, price):
        self.price = price
```

Simplified lookup for `book1.category` begins with the instance and can then find the attribute on its class (and later, base classes). This is similar in spirit to name lookup but is not the LEGB rule itself.

```text
book1.category
     |
     v
  book1 instance
     |
     v
  Book class
```

A class attribute should represent information that belongs to the class/model rather than information unique to each object. The decision is about ownership and meaning, not merely avoiding repeated values.

Class attributes are intentionally not explored further in this checkpoint; they will be revisited when there is a concrete reason to use them.

## 9. Validation and object responsibility

A method that changes object state can enforce rules before performing the change.

```python
class Book:
    def increase_price(self, amount):
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        self.price = self.price + amount
```

The order matters:

```text
validate
   |
   v
perform state change
```

If invalid input causes an exception before the assignment, the object's state is not changed by that operation.

This is the beginning of a larger object-oriented design idea: the object can be responsible for maintaining rules about its own state.

## 10. Early encapsulation mental model

Python allows ordinary instance attributes to be changed directly:

```python
book1.price = -100
```

A validation rule inside `increase_price()` cannot prevent this direct assignment.

This exposes the next design problem:

> How can an object control access to state when that state has invariants that must remain valid?

That question leads naturally into encapsulation and controlled attribute access. The mechanism is deliberately not included here yet.

## Engineering takeaway

The core mental model established in this checkpoint is:

```text
Class
  |
  +-- defines behavior and the model
  |
  +-- methods
  |
  v
Objects / instances
  |
  +-- each has its own identity
  +-- each holds its own instance state
  |
  v
Methods operate through `self`
  |
  +-- may read state
  +-- may return derived information
  +-- may modify state
  +-- may enforce rules before modifying state
```

The goal is not to memorize these as isolated facts. The goal is to reason about **who owns state, which object a behavior operates on, whether a method changes state, and where an object's rules should be enforced**.
