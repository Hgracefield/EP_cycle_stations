import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/demo_nav_scaffold.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class AuthPage extends StatelessWidget {
  const AuthPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const DemoNavScaffold(
      title: 'Auth Page',
      currentRoute: RouterNames.auth,
    );
  }
}
