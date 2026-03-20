import 'package:flutter/material.dart';
import 'package:seoul_bike_prediction/routes/router_names.dart';

class AuthPage extends StatelessWidget {
  const AuthPage({super.key});

  static const List<_AuthNavItem> _navItems = <_AuthNavItem>[
    _AuthNavItem(label: 'Sign Up', routeName: RouterNames.authSign),
    _AuthNavItem(label: 'Find Info', routeName: RouterNames.authFindInfo),
    _AuthNavItem(label: 'Dashboard', routeName: RouterNames.dashboard),
    _AuthNavItem(label: 'Map User', routeName: RouterNames.mapForUser),
    _AuthNavItem(label: 'Map Worker', routeName: RouterNames.mapForWorker),
    _AuthNavItem(label: 'Reservation', routeName: RouterNames.reservation),
    _AuthNavItem(label: 'Settings', routeName: RouterNames.settings),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Auth Page'),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Move page',
            onSelected: (routeName) => Navigator.pushNamed(context, routeName),
            itemBuilder: (context) => _navItems
                .map(
                  (item) => PopupMenuItem<String>(
                    value: item.routeName,
                    child: Text(item.label),
                  ),
                )
                .toList(),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Page Hub', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            const Text('앱바 메뉴나 아래 버튼으로 각 페이지를 바로 이동할 수 있습니다.'),
            const SizedBox(height: 24),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: _navItems
                  .map(
                    (item) => FilledButton(
                      onPressed: () =>
                          Navigator.pushNamed(context, item.routeName),
                      child: Text(item.label),
                    ),
                  )
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _AuthNavItem {
  const _AuthNavItem({required this.label, required this.routeName});

  final String label;
  final String routeName;
}
