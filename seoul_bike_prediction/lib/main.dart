import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/app_router.dart';

void main() {
  runApp(const SeoulBikePredictionApp());
}

class SeoulBikePredictionApp extends StatelessWidget {
  const SeoulBikePredictionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Seoul Bike Prediction',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.green),
      ),
      initialRoute: AppRouter.initialRoute,
      onGenerateRoute: AppRouter.onGenerateRoute,
    );
  }
}
