import { defineRailway, github, postgres, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const GestorFinanzas = github("lordPobre/GestorFinanzas", { branch: "main", checkSuites: true });

  const Postgres = postgres("Postgres", { region: "us-west2" });
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "us-west2", sizeMB: 5000 });

  const nixpacks = { buildEnvironment: "V3", builder: "NIXPACKS" } as const;

  const tarea = (nombre: string, comando: string, horario: string, privado: string) =>
    service(nombre, {
      source: GestorFinanzas,
      build: nixpacks,
      start: comando,
      replicas: { "us-west2": 1 },
      deploy: { cronSchedule: horario, restartPolicyType: "NEVER" },
      networking: { privateNetworkEndpoint: privado },
    });

  const web = service("web", {
    source: GestorFinanzas,
    build: { ...nixpacks, buildCommand: "python manage.py collectstatic --noinput" },
    start: "gunicorn core.wsgi --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60",
    healthcheck: "/salud/",
    healthcheckTimeout: 30,
    preDeploy: "python manage.py createcachetable && python manage.py migrate --noinput",
    replicas: { "us-west2": 1 },
    deploy: { restartPolicyMaxRetries: 3 },
    domains: ["fintora.cl", "www.fintora.cl"],
  });

  const Cola = service("Cola", {
    source: GestorFinanzas,
    build: nixpacks,
    start: "python manage.py qcluster",
    replicas: { "us-west2": 1 },
    deploy: { limitOverride: { containers: { cpu: 4, memoryBytes: 2000000000 } } },
    networking: { privateNetworkEndpoint: "gestorfinanzas-8641177e" },
  });

  const respaldo = service("respaldo", {
    source: GestorFinanzas,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/railway/Dockerfile.respaldo" } as const,
    start: "python manage.py respaldar_postgres",
    replicas: { "us-west2": 1 },
    deploy: { cronSchedule: "0 7 * * *", restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "gestorfinanzas-cd8c" },
  });

  const Recordatorios = tarea("Recordatorios", "python manage.py enviar_recordatorios --hilos 8 --a-las 9", "0 * * * *", "recordatorios");
  const avisar_pagos = tarea("avisar_pagos", "python manage.py avisar_pagos", "0 13 * * *", "gestorfinanzas");
  const limpieza_audios = tarea("limpieza_audios", "python manage.py limpiar_audios", "0 * * * *", "audios");
  const limpiar_avatares = tarea("limpiar_avatares", "python manage.py limpiar_avatares_huerfanos", "0 4 * * 0", "gestorfinanzas-4dd3");
  const limpiar_inactividad = tarea("limpiar_inactividad", "python manage.py limpiar_inactivas", "0 12 * * *", "limpiarinactividad");
  const servicio_limpieza = tarea("servicio_limpieza", "python manage.py limpieza_diaria", "30 6 * * *", "serviciolimpieza");

  return project("Fintora", {
    variables: { managed: false },
    resources: [web, Cola, respaldo, Recordatorios, avisar_pagos, limpieza_audios, limpiar_avatares, limpiar_inactividad, servicio_limpieza, Postgres, postgresVolume],
  });
});
