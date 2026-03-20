import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/demo_nav_scaffold.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class MapForWorkerPage extends StatelessWidget {
  const MapForWorkerPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const DemoNavScaffold(
      title: 'Map For Worker Page',
      currentRoute: RouterNames.mapForWorker,
    );
  }
}
