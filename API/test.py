# a = [i for i in range(1,11)]
# print(a)
#
# a = {i:k for i,k in enumerate(range(1,11))}
# print(a)


# for i in range(2,101):
#     is_p = True
#
#     for j in range(2,i):
#         if i % j == 0:
#             is_p = False
#             break
#     if is_p:
#         print(i)
#
# res1 = [i%2==0 for i in range(2,10) for j in range(2,i)]
# print(res1)
# func = lambda i:i*i
#
#
#
#
#
# for i in range(2,101):
#     for j in range(2,i):
#         if i % j != 0:
#             print(1)
#         else:
#             break
#     else:
#         print(i)

res = [
    i for i in range(2, 101)
    if all(i % j != 0 for j in range(2, i))
]

print(all(10 % j != 0 for j in range(2, 10)))
# res1 = []
# for i in range(1,100001):
#     str_i = str(i)
#     wei = len(str(i))
#     sum = 0
#     for j in range(wei):
#         sum +=int(str_i[j]) ** wei
#
#     if sum == i:
#         res1.append(i)
#
# res2 = []
# for i in range(1,100001):
#     # 判断位数
#     r = i
#     n = 0
#     while r != 0:
#         n += 1
#         r = r // 10
#
#     # 累加
#     r = i
#     s = 0
#     while r != 0:
#         s += (r % 10) ** n
#         r = r // 10
#
#     if s == i:
#         res2.append(i)
#
# print(res1)
# print(res2)

ls = [i for i in range(2,101) if all(i % j!=0 for j in range(2,int(i**0.5)+1))]
print(ls)