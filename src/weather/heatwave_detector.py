class HeatwaveDetector:

    TMAX_THRESHOLD = 42.0
    TMIN_THRESHOLD = 28.0
    MIN_DURATION = 2

    def detect(self, weather_data):
        """
        Detect heatwave periods from daily weather data.

        A heatwave is detected when at least 2 consecutive
        days meet either:
        - Tmax >= 42°C
        - Tmin >= 28°C
        """

        if not weather_data:
            return []

        heatwave_days = []

        for day in weather_data:

            is_heatwave = (
                day["tmax"] >= self.TMAX_THRESHOLD
                or
                day["tmin"] >= self.TMIN_THRESHOLD
            )

            heatwave_days.append({
                **day,
                "is_heatwave_day": is_heatwave
            })

        events = []
        current_event = []

        for day in heatwave_days:

            if day["is_heatwave_day"]:

                current_event.append(day)

            else:

                if len(current_event) >= self.MIN_DURATION:
                    events.append(current_event)

                current_event = []

        # Handle event ending on final forecast day
        if len(current_event) >= self.MIN_DURATION:
            events.append(current_event)

        return events

    def get_longest_heatwave(self, weather_data):

        events = self.detect(weather_data)

        if not events:
            return []

        return max(
            events,
            key=len
        )