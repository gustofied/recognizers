def range_gen(start, end, step):
    i = start
    while i < end:
        yield i
        i += step

values = range_gen(0, 10, 2)

print(next(values))  
print(next(values)) 
print(next(values))  

print("-#-")
for i in range_gen(10, 20, 2):
    print(i)

print("-#-")
def naturals():
    n = 0
    while True:
        yield n
        n += 1

for i in naturals():
    print(i)
    if i > 12:
        break

print("-#-")

# Dum dum fnction

def echo():
    print("lets go")
    while True:
        line = yield
        print(line)

gen = echo()
gen.send(None)
gen.send("Blah")
gen.send("Blah")
gen.send("Blah")