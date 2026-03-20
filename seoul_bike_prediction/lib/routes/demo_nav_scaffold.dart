import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class DemoNavScaffold extends StatelessWidget {
  const DemoNavScaffold({
    super.key,
    required this.title,
    required this.currentRoute,
  });

  final String title;
  final String currentRoute;

  static const List<_NavItem> _items = <_NavItem>[
    _NavItem(label: 'Auth', routeName: RouterNames.auth),
    _NavItem(label: 'Sign Up', routeName: RouterNames.authSign),
    _NavItem(label: 'Find Info', routeName: RouterNames.authFindInfo),
    _NavItem(label: 'Dashboard', routeName: RouterNames.dashboard),
    _NavItem(label: 'Map User', routeName: RouterNames.mapForUser),
    _NavItem(label: 'Map Worker', routeName: RouterNames.mapForWorker),
    _NavItem(label: 'Reservation', routeName: RouterNames.reservation),
    _NavItem(label: 'Settings', routeName: RouterNames.settings),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: theme.textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Current route: $currentRoute',
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: _items.map((item) {
                final isCurrent = item.routeName == currentRoute;

                return FilledButton.tonal(
                  onPressed: isCurrent
                      ? null
                      : () => Navigator.pushNamed(context, item.routeName),
                  child: Text(item.label),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavItem {
  const _NavItem({
    required this.label,
    required this.routeName,
  });

  final String label;
  final String routeName;
}
