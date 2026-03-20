import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/features/auth/auth_find_info.dart';
import 'package:seoul_bike_prediction/features/auth/auth_page.dart';
import 'package:seoul_bike_prediction/features/auth/auth_sign_page.dart';
import 'package:seoul_bike_prediction/features/dashboard/dashboard_page.dart';
import 'package:seoul_bike_prediction/features/map_for_user/map_for_user_page.dart';
import 'package:seoul_bike_prediction/features/map_for_worker/map_for_worker_page.dart';
import 'package:seoul_bike_prediction/features/reservation/reservation_page.dart';
import 'package:seoul_bike_prediction/features/settings/setting_page.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class PageHub {
  static Widget page(String routeName) {
    switch (routeName) {
      case RouterNames.auth:
        return const AuthPage();
      case RouterNames.authSign:
        return const AuthSignPage();
      case RouterNames.authFindInfo:
        return const AuthFindInfoPage();
      case RouterNames.dashboard:
        return const DashboardPage();
      case RouterNames.mapForUser:
        return const MapForUserPage();
      case RouterNames.mapForWorker:
        return const MapForWorkerPage();
      case RouterNames.reservation:
        return const ReservationPage();
      case RouterNames.settings:
        return const SettingPage();
      default:
        return const _UnknownRoutePage();
    }
  }
}

class _UnknownRoutePage extends StatelessWidget {
  const _UnknownRoutePage();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Text('Page not found'),
      ),
    );
  }
}
