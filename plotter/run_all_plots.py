"""
    Script to generate all plots. It runs all other scripts inside the Plotter module except for
    the plot_animation, the plot_output_data and the support_plotter scripts.
"""

from plotter import get_training_time_traffic, plot_training_time_traffic, plot_cdf_reward, plot_reward_per_request, \
    plot_moving_avg, plot_moving_avg_for_params

get_training_time_traffic.main()

plot_training_time_traffic.main()

plot_cdf_reward.main()

plot_moving_avg.main()

plot_moving_avg_for_params.main()

plot_reward_per_request.main()
