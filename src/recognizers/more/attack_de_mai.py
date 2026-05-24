# stuff I want to use 

def count_to(n):
    numbers = []
    count = 1
    while count <= n:
        numbers.append(count)
        count+= 1
        print(numbers)
    return numbers

number = int(input("give me a numbers"))

for n in count_to(number):
    print(n)