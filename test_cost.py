from appliance.routing.cost_calculation import CostCalculation


calculator = CostCalculation()

path_metrics = {
    "S1 -> S2 -> S4": {
        "delay": 10,
        "packet_loss": 2,
        "utilization": 80
    },

    "S1 -> S3 -> S4": {
        "delay": 5,
        "packet_loss": 0,
        "utilization": 30
    }
}

costs = calculator.calculate_all_path_costs(path_metrics)

print("\nPATH COSTS")
print("----------")

for path, cost in costs.items():
    print("{} : {:.4f}".format(path, cost))

best_path = calculator.select_best_path(costs)

print("\nBEST PATH")
print("----------")
print(best_path)
