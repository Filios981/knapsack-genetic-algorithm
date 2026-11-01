from knapsack_ga.models import GAParams, KnapsackProblem, MutationMethod


def test_default_params_match_assignment():
    params = GAParams()

    assert params.crossover_prob == 0.8
    assert params.mutation_prob == 0.2
    assert params.mutation_method is MutationMethod.PER_INDIVIDUAL  # jak na zajęciach


def test_problem_size_is_number_of_items(p02_problem: KnapsackProblem):
    assert p02_problem.size == 5
