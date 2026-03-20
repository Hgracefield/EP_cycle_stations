import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/page_hub.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class AppRouter {
  static const String initialRoute = RouterNames.auth;

  static Route<dynamic> onGenerateRoute(RouteSettings settings) {
    final routeName = settings.name ?? initialRoute;

    return MaterialPageRoute(
      builder: (_) => PageHub.page(routeName),
      settings: settings,
    );
  }
}
