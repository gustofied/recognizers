def range_gen(start, end, step):
    i = start
    while i < end:
        yield i
        i += step

values = range_gen(0, 10, 2)

print(next(values))  
print(next(values)) 
print(next(values))  


for i in range_gen(10, 20, 2):
    print(i)