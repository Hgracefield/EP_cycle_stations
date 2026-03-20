import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/demo_nav_scaffold.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class SettingPage extends StatelessWidget {
  const SettingPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const DemoNavScaffold(
      title: 'Setting Page',
      currentRoute: RouterNames.settings,
    );
  }
}
