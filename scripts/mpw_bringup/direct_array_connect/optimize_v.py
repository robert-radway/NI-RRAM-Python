from scipy.optimize import minimize

# Objective function: Minimize VUL
def objective(x):
    vul = x[0]
    return vul

# Constraints
def constraint1(x):
    return x[0] + 2  # VWL - VSL = -2

def constraint2(x):
    return x[0] + 2.2  # VBL - VSL = -2.2

def constraint3(x):
    return x[0] - x[0] + 2  # VUL - VSL > 2

constraints = [{'type': 'eq', 'fun': constraint1},
               {'type': 'eq', 'fun': constraint2},
               {'type': 'ineq', 'fun': constraint3}]

# Initial guess
x0 = [0]

# Optimization
result = minimize(objective, x0, constraints=constraints)

# Extract the values
vul = result.x[0]
vwl = vul - 2
vbl = vul - 2.2
vsl = vul - 2

print("VWL:", vwl)
print("VBL:", vbl)
print("VSL:", vsl)
print("VUL:", vul)
