import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/demo_nav_scaffold.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class MapForUserPage extends StatelessWidget {
  const MapForUserPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const DemoNavScaffold(
      title: 'Map For User Page',
      currentRoute: RouterNames.mapForUser,
    );
  }
}
