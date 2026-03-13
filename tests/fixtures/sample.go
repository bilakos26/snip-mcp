package main

import "fmt"

type Animal struct {
	Name string
	Age  int
}

type Speaker interface {
	Speak() string
}

func (a *Animal) Speak() string {
	return fmt.Sprintf("%s says hello", a.Name)
}

func NewAnimal(name string, age int) *Animal {
	return &Animal{Name: name, Age: age}
}
